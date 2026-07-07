"""Background version-check and upgrade utilities for ajo-cli.

Checks the PyPI JSON API for newer releases in a non-blocking daemon
thread, caches the result for 24 hours, and provides the ``ajo upgrade``
command with environment-correct subprocess delegation.

Usage::

    # At startup (non-blocking):
    from ajo.core.updater import check_in_background

    check_in_background()

    # On demand:
    from ajo.core.updater import check_for_updates

    latest, is_newer = await check_for_updates()
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ajo import __version__
from ajo.core.config import CONFIG_DIR

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

#: How many hours between PyPI checks.
CHECK_INTERVAL_HOURS: int = 24

#: PyPI JSON API URL for ajo-cli.
PYPI_JSON_URL: str = "https://pypi.org/pypi/ajo-cli/json"

#: HTTP request timeout in seconds.
REQUEST_TIMEOUT: int = 5

#: Cache file location.
CACHE_FILE: Path = CONFIG_DIR / "update_cache.json"

#: Environment variable to silence all update checks.
NO_UPDATE_CHECK_ENV: str = "AJO_NO_UPDATE_CHECK"

#: Module-level cache for the latest check result so ``_check_in_background``
#: can write it and ``get_cached_update`` can read it without hitting the disk
#: multiple times.
_cache: dict[str, Any] | None = None


# ── Version parsing ────────────────────────────────────────────────────────


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable tuple of ints.

    Args:
        version_str: e.g. ``"3.3.0"`` or ``"3.3.0rc1"``.

    Returns:
        A tuple of integers, e.g. ``(3, 3, 0)``.  Non-numeric segments
        (``rc1``, ``a1``, etc.) are silently ignored so pre-releases still
        compare by their numeric prefix.
    """
    parts: list[int] = []
    for segment in version_str.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            # Strip non-numeric suffix (e.g. "0rc1" → 0)
            numeric = ""
            for ch in segment:
                if ch.isdigit():
                    numeric += ch
                else:
                    break
            if numeric:
                parts.append(int(numeric))
            # Ignore the rest (rc, dev, post, etc.)
            break
    return tuple(parts)


# ── Should-check predicate ─────────────────────────────────────────────────


def should_check_updates(config: dict[str, Any] | None = None) -> bool:
    """Determine whether the background update check should run.

    Returns ``False`` (suppress check) when:

    * The ``AJO_NO_UPDATE_CHECK`` env var is set to ``"1"``, ``"true"``,
      or ``"yes"`` (case-insensitive).
    * The user's config has ``check_updates: false``.

    In all other cases returns ``True`` (check is allowed).

    Args:
        config: A config dict (e.g. ``ConfigManager._data``).  ``None``
            means "no config loaded" — only the env var is consulted.
    """
    # 1. Environment variable (highest precedence)
    env_val = os.environ.get(NO_UPDATE_CHECK_ENV, "").lower().strip()
    if env_val in ("1", "true", "yes"):
        return False

    # 2. Config file
    if config is not None:
        return bool(config.get("check_updates", True))

    return True


# ── PyPI check ─────────────────────────────────────────────────────────────


def check_for_updates(
    *,
    force: bool = False,
    config: dict[str, Any] | None = None,
) -> tuple[str, bool] | None:
    """Fetch the latest version from PyPI and compare with the current version.

    This function makes a **synchronous HTTP request** — it must be called
    from a thread (not the main asyncio event loop).  The result is cached
    to disk and in-memory so subsequent calls within the same process and
    across CLI invocations are near-instant.

    Args:
        force: If ``True``, ignore the cache and re-fetch from PyPI.
        config: Config dict for the ``should_check_updates`` gate.

    Returns:
        ``(latest_version, is_newer)`` on success, or ``None`` if the
        check was suppressed or failed (network error, parse error, …).

        ``is_newer`` is ``True`` when *latest_version* > *current_version*.
    """
    global _cache

    # ── Gate ───────────────────────────────────────────────────────────
    if not force and not should_check_updates(config=config):
        return None

    # ── Check in-memory cache ─────────────────────────────────────────
    if not force and _cache is not None:
        latest = _cache.get("latest_version", "")
        if latest:
            return latest, _cache.get("is_newer", False)

    # ── Check disk cache ──────────────────────────────────────────────
    if not force:
        cached = _read_cache()
        if cached is not None:
            _cache = cached
            latest = cached.get("latest_version", "")
            if latest:
                return latest, cached.get("is_newer", False)

    # ── Fetch from PyPI ───────────────────────────────────────────────
    try:
        req = urllib.request.Request(
            PYPI_JSON_URL,
            headers={"User-Agent": f"ajo-cli/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

        latest_version: str = data.get("info", {}).get("version", "")
        if not latest_version:
            logger.warning("PyPI response missing 'info.version' field")
            return None

        current_parsed = parse_version(__version__)
        latest_parsed = parse_version(latest_version)
        is_newer = latest_parsed > current_parsed

        # Write cache
        _cache = {
            "latest_version": latest_version,
            "current_version": __version__,
            "is_newer": is_newer,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_cache(_cache)

        return latest_version, is_newer

    except urllib.error.URLError as exc:
        logger.debug("PyPI check failed (network): %s", exc)
    except json.JSONDecodeError as exc:
        logger.warning("PyPI response was not valid JSON: %s", exc)
    except Exception as exc:
        logger.debug("PyPI check failed (unexpected): %s", exc)

    return None


# ── Background check ───────────────────────────────────────────────────────


def check_in_background(
    config: dict[str, Any] | None = None,
) -> threading.Thread | None:
    """Start a non-blocking daemon thread to check for updates.

    The thread is a daemon so it will not prevent the process from exiting.
    If the check is suppressed by config or env var, no thread is started.

    Safe to call multiple times — subsequent calls are no-ops if a check
    has already been performed within the same process.

    Args:
        config: Config dict for the ``should_check_updates`` gate.

    Returns:
        The daemon :class:`threading.Thread` if one was started,
        ``None`` otherwise.
    """
    global _cache

    # Already checked in this process?
    if _cache is not None:
        return None

    # Gate
    if not should_check_updates(config=config):
        logger.debug("Background update check suppressed")
        return None

    # Check disk cache before firing a thread
    cached = _read_cache()
    if cached is not None:
        _cache = cached
        # Cache is still fresh enough — no need for a thread
        checked_str = cached.get("checked_at", "")
        if checked_str:
            try:
                checked = datetime.fromisoformat(checked_str)
                age_hours = (
                    datetime.now(timezone.utc) - checked
                ).total_seconds() / 3600
                if age_hours < CHECK_INTERVAL_HOURS:
                    logger.debug("Update cache is fresh (%.1f hours old)", age_hours)
                    return None
            except (ValueError, TypeError):
                pass  # Corrupt timestamp — re-check

    # Fire a daemon thread
    thread = threading.Thread(
        target=_background_check,
        args=(config,),
        daemon=True,
        name="ajo-update-check",
    )
    thread.start()
    return thread


def _background_check(config: dict[str, Any] | None) -> None:
    """Target for the daemon thread — runs :func:`check_for_updates`."""
    try:
        check_for_updates(force=True, config=config)
        logger.debug("Background update check completed")
    except Exception:
        logger.debug("Background update check failed", exc_info=True)


# ── Caching ────────────────────────────────────────────────────────────────


def _read_cache() -> dict[str, Any] | None:
    """Read the update cache from disk, or return ``None`` on any error."""
    try:
        if CACHE_FILE.is_file():
            raw = CACHE_FILE.read_text(encoding="utf-8")
            return json.loads(raw)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
        pass
    return None


def _write_cache(data: dict[str, Any]) -> None:
    """Write the update cache to disk, swallowing errors."""
    try:
        CACHE_FILE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, PermissionError):
        pass


def get_cached_update() -> tuple[str, bool] | None:
    """Return the cached update result, or ``None`` if no cache exists.

    This is the main public API for the CLI to check whether a newer
    version was discovered by a previous background check.

    Returns:
        ``(latest_version, is_newer)`` or ``None``.
    """
    global _cache

    data = _cache
    if data is None:
        data = _read_cache()
        if data is None:
            return None
        _cache = data

    latest = data.get("latest_version", "")
    if not latest:
        return None

    return latest, data.get("is_newer", False)


# ── Formatting ─────────────────────────────────────────────────────────────


def format_update_message(latest: str) -> str:
    """Return a Rich-formatted notification string for an available update.

    Args:
        latest: The latest version available on PyPI.

    Returns:
        A string ready for ``console.print()``.
    """
    return (
        f"[bold yellow]⟳ Update available:[/] [cyan]v{__version__}[/] → "
        f"[green]v{latest}[/]\n"
        f"  [dim]Run [bold]ajo upgrade[/] to update.[/]"
    )
