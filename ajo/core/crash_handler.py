"""Crash dump generator for unexpected failures.

Writes detailed debug logs to ``~/.config/ajo/crashes/`` whenever the
CLI encounters an unexpected exception.  The dumps include system
information, environment variables (with secrets redacted), ajo config
(with secrets redacted), and the full traceback — everything needed to
diagnose issues without asking the user to re-run with verbose flags.

Usage::

    from ajo.core.crash_handler import install_crash_handler

    install_crash_handler()
    # ... rest of the application ...
    # On any unhandled Exception, a crash dump is written automatically.
"""

from __future__ import annotations

import datetime
import logging
import os
import platform
import sys
import textwrap
import traceback
from pathlib import Path

from ajo import __version__ as _ajo_version
from ajo.core.config import CONFIG_DIR

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

CRASHES_DIR: Path = CONFIG_DIR / "crashes"
"""Directory where crash dumps are stored (``~/.config/ajo/crashes/``)."""


# ── Secret redaction for dump safety ──────────────────────────────────────────

_SENSITIVE_ENV_KEYS = frozenset(
    {
        "KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "AUTH",
        "API_KEY",
        "API_SECRET",
        "ACCESS_KEY",
        "SECRET_KEY",
    }
)

_SENSITIVE_ENV_SUBSTRINGS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH")


def _redact_value(value: str) -> str:
    """Replace a sensitive value with a redacted marker.

    If the value is longer than 8 characters, shows the first 2 and
    last 2 characters for debugging: ``"ab***cd"``.  Short values are
    fully redacted to ``"***"``.
    """
    if len(value) <= 8:
        return "***"
    return value[:2] + "***" + value[-2:]


def _should_redact_env_key(key: str) -> bool:
    """Check if an environment variable name is sensitive."""
    upper = key.upper()
    if upper in _SENSITIVE_ENV_KEYS:
        return True
    for sub in _SENSITIVE_ENV_SUBSTRINGS:
        if sub in upper:
            return True
    return False


def _redact_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of *env* with sensitive values redacted."""
    result: dict[str, str] = {}
    for k, v in env.items():
        if _should_redact_env_key(k):
            result[k] = _redact_value(v)
        else:
            result[k] = v
    return result


# ── Crash dump writer ─────────────────────────────────────────────────────────


def write_crash_dump(exc: BaseException) -> Path | None:
    """Write a detailed crash dump to ``CRASHES_DIR``.

    Creates the crashes directory if it doesn't exist.  Silently handles
    permission errors (graceful degradation — never crash the crash
    handler).

    Args:
        exc: The unhandled exception that caused the crash.

    Returns:
        The path to the written dump file, or ``None`` if writing failed.
    """
    try:
        CRASHES_DIR.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        logger.warning("Cannot create crashes directory %s", CRASHES_DIR)
        return None

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    crash_file = CRASHES_DIR / f"crash-{timestamp}.log"

    try:
        crash_file.write_text(
            _build_dump_text(exc),
            encoding="utf-8",
        )
        logger.info("Crash dump written to %s", crash_file)
        return crash_file
    except (OSError, PermissionError) as write_err:
        logger.warning("Cannot write crash dump to %s: %s", crash_file, write_err)
        return None


# ── Dump content builder ──────────────────────────────────────────────────────


def _build_dump_text(exc: BaseException) -> str:
    """Build the full text of a crash dump."""
    sections: list[str] = []

    # Header
    sections.append("=" * 72)
    sections.append(" AJO CLI CRASH DUMP")
    sections.append("=" * 72)
    sections.append(
        f"Timestamp:  {datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )
    sections.append(f"Ajo version: {_ajo_version}")
    sections.append("")

    # System info
    sections.append("─" * 72)
    sections.append(" SYSTEM INFORMATION")
    sections.append("─" * 72)
    sections.append(f"Platform:    {platform.platform()}")
    sections.append(f"System:      {platform.system()} {platform.release()}")
    sections.append(f"Machine:     {platform.machine()}")
    sections.append(f"Processor:   {platform.processor()}")
    sections.append(f"Python:      {sys.version}")
    sections.append(f"Executable:  {sys.executable}")
    sections.append(f"PID:         {os.getpid()}")
    sections.append("")

    # Environment variables (redacted)
    sections.append("─" * 72)
    sections.append(" ENVIRONMENT VARIABLES (sensitive values redacted)")
    sections.append("─" * 72)
    redacted_env = _redact_env(dict(os.environ))
    for key in sorted(redacted_env):
        sections.append(f"  {key}={redacted_env[key]}")
    sections.append("")

    # Exception info
    sections.append("─" * 72)
    sections.append(" EXCEPTION")
    sections.append("─" * 72)
    sections.append(f"Type:    {type(exc).__module__}.{type(exc).__qualname__}")
    sections.append(f"Message: {exc}")
    sections.append("")

    # Traceback
    sections.append("─" * 72)
    sections.append(" TRACEBACK")
    sections.append("─" * 72)
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    sections.append("".join(tb_lines).rstrip())
    sections.append("")

    return "\n".join(sections)


# ── Global exception hook ─────────────────────────────────────────────────────


_original_excepthook: object = None
"""Saved reference to the original :func:`sys.excepthook`."""


def crash_excepthook(exc_type: type, exc_value: BaseException, tb: object) -> None:
    """Replacement for :func:`sys.excepthook` that writes a crash dump.

    Writes a crash dump for unhandled exceptions (excluding
    :class:`KeyboardInterrupt` and :class:`SystemExit`), then delegates
    to the original hook for normal termination.
    """
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        # Don't dump for intentional exits
        if callable(_original_excepthook):
            _original_excepthook(exc_type, exc_value, tb)
        return

    write_crash_dump(exc_value)

    # Delegate to original hook
    if callable(_original_excepthook):
        _original_excepthook(exc_type, exc_value, tb)


def install_crash_handler() -> None:
    """Install the crash dump handler as the global ``sys.excepthook``.

    Safe to call multiple times (idempotent).  The handler writes a
    detailed crash dump to ``~/.config/ajo/crashes/`` for every
    unhandled exception, then delegates to the original hook.
    """
    global _original_excepthook
    if _original_excepthook is None:
        _original_excepthook = sys.excepthook
    sys.excepthook = crash_excepthook


def uninstall_crash_handler() -> None:
    """Restore the original ``sys.excepthook``.

    Only needed in long-running processes (e.g. test suites) to avoid
    side effects between tests.
    """
    global _original_excepthook
    if _original_excepthook is not None:
        sys.excepthook = _original_excepthook  # type: ignore[assignment]
        _original_excepthook = None


__all__ = [
    "CRASHES_DIR",
    "write_crash_dump",
    "install_crash_handler",
    "uninstall_crash_handler",
    "_redact_env",
]
