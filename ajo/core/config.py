"""Persistent configuration manager for ajo-cli.

Reads/writes ``~/.config/ajo/config.json`` with full error tolerance for
permission errors, missing directories, and corrupt JSON files.

Usage::

    from ajo.core.config import ConfigManager, get_config

    config = ConfigManager()          # auto-loads from disk
    config.set("nerd_fonts", True, auto_save=True)
    val = config.get("nerd_fonts", default=False)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# ── Paths ──────────────────────────────────────────────────────────────────
# Both are module-level so tests can monkey-patch them before init.

CONFIG_DIR: Path = Path("~/.config/ajo").expanduser().resolve()
CONFIG_FILE: Path = CONFIG_DIR / "config.json"

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict = {
    "version": 1,
    "nerd_fonts": None,  # None = unset (prompt on first interactive use)
    "theme": None,
    "check_updates": True,
    "updated_at": None,
}

# ── Global singleton reference ─────────────────────────────────────────────

_global_config: ConfigManager | None = None


def get_config() -> ConfigManager | None:
    """Return the global :class:`ConfigManager` instance, or *None* if not yet
    initialised.

    Safe to call from anywhere — returns ``None`` when called before
    :class:`ConfigManager` has been constructed, which causes icon
    resolution to fall back to auto-detection.
    """
    return _global_config


# ═════════════════════════════════════════════════════════════════════════════
# ConfigManager
# ═════════════════════════════════════════════════════════════════════════════


class ConfigManager:
    """Reads/writes ``~/.config/ajo/config.json`` with full error tolerance.

    **Thread safety:** the instance is intended to be created once at startup
    and then read-only for the rest of the process.  The global reference
    ``_global_config`` is set during ``__init__`` so that :func:`get_config`
    becomes available immediately to any code that needs it.
    """

    def __init__(self) -> None:
        global _global_config
        self._data: dict = dict(DEFAULT_CONFIG)
        self._dirty: bool = False
        self._load()
        _global_config = self

    # ── Public API ──────────────────────────────────────────────────────────

    def get(self, key: str, default: object = None) -> object:
        """Return a config value, or *default* if the key is missing or ``None``.

        Args:
            key: Config key (e.g. ``"nerd_fonts"``).
            default: Value returned when the key does not exist or is ``None``.

        Returns:
            The stored value or *default*.
        """
        value = self._data.get(key, default)
        if value is None and key in DEFAULT_CONFIG:
            return default
        return value

    def set(self, key: str, value: object, *, auto_save: bool = False) -> None:
        """Set a config value and optionally persist to disk immediately.

        Args:
            key: Config key.
            value: Any JSON-serialisable value.
            auto_save: If ``True``, call :meth:`save` after setting.
        """
        self._data[key] = value
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._dirty = True
        if auto_save:
            self.save()

    def save(self) -> None:
        """Write current config to disk.

        This is a no-op if the data has not been modified since the last save.
        Errors (permission, read-only filesystem, etc.) are silently swallowed
        so the CLI never crashes because of a config write failure.
        """
        if not self._dirty:
            return
        try:
            CONFIG_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._dirty = False
        except (OSError, PermissionError):
            pass  # Graceful degradation — never crash

    def is_first_run(self) -> bool:
        """Return ``True`` if ``nerd_fonts`` has never been set (first-time use).

        This is the signal to show the interactive Nerd Font preference prompt.
        """
        return self._data.get("nerd_fonts") is None

    def __repr__(self) -> str:
        nf = self._data.get("nerd_fonts", "MISSING")
        return f"<ConfigManager nerd_fonts={nf!r}>"

    # ── Internal ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load config from ``CONFIG_FILE``, falling back to defaults on any error."""
        try:
            if CONFIG_FILE.is_file():
                raw = CONFIG_FILE.read_text(encoding="utf-8")
                loaded: dict = json.loads(raw)
                # Merge so new default keys are always present
                for k, v in DEFAULT_CONFIG.items():
                    loaded.setdefault(k, v)
                self._data = loaded
        except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
            self._data = dict(DEFAULT_CONFIG)
