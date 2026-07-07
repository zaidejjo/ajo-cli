"""Logging configuration for the ajo-cli.

Provides :func:`setup_logging` which configures Python's ``logging``
module based on verbosity flags passed from the CLI.

Verbosity levels (mapped to stdlib logging levels):

    - ``-q`` / ``--quiet``:  **ERROR**   (only errors and critical messages)
    - (default, no flag):    **WARNING**  (warnings + errors + critical)
    - ``-v``:                **INFO**     (high-level progress)
    - ``-vv``:               **DEBUG**    (detailed debug output)

Usage::

    from ajo.core.logging_config import setup_logging

    setup_logging(verbosity=1)  # INFO level
    logger = logging.getLogger("ajo.scaffolding")
    logger.info("Starting scaffold...")
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO


# ── Verbosity → stdlib level mapping ─────────────────────────────────────

VERBOSITY_MAP: dict[int, int] = {
    -1: logging.ERROR,  # -q / --quiet
    0: logging.WARNING,  # default
    1: logging.INFO,  # -v
    2: logging.DEBUG,  # -vv
}

DEFAULT_VERBOSITY: int = 0

# ── Log format ───────────────────────────────────────────────────────────

SIMPLE_FORMAT: str = "%(levelname)s: %(message)s"
DETAILED_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ── Logger name hierarchy ────────────────────────────────────────────────

ROOT_LOGGER_NAME: str = "ajo"

# Loggers that are particularly noisy at DEBUG level — kept at INFO
_QUIET_LOGGERS: list[str] = [
    "ajo.ui",
    "ajo.detector",
]


# ── Public API ─────────────────────────────────────────────────────────────


def setup_logging(
    verbosity: int = DEFAULT_VERBOSITY,
    *,
    log_file: str | None = None,
    stream: TextIO | None = None,
    force: bool = False,
) -> None:
    """Configure the ``ajo`` logger hierarchy.

    Call this once at startup, **after** CLI arguments have been parsed.
    Idempotent on subsequent calls unless *force* is ``True``.

    Args:
        verbosity: Integer verbosity level. -1 = quiet, 0 = normal,
                   1 = verbose, 2 = very verbose / debug.
        log_file: Optional path to a file for persistent logs.
        stream: Output stream (defaults to ``sys.stderr``).
        force: Reconfigure even if logging was already set up.
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)

    # Avoid duplicate configuration
    if logger.handlers and not force:
        return

    level = VERBOSITY_MAP.get(verbosity, logging.DEBUG)
    logger.setLevel(level)

    # Remove any pre-existing handlers on the ajo logger
    if force:
        logger.handlers.clear()

    if not logger.handlers:
        _add_console_handler(logger, level, stream or sys.stderr)

        if log_file:
            _add_file_handler(logger, level, log_file)

    # Suppress noisy sub-loggers at DEBUG to avoid spam
    _apply_quiet_overrides(level)

    # Prevent propagation to the root logger so we don't get duplicate
    # messages from library code (e.g. ``rich``, ``urllib3``).
    logger.propagate = False


def set_verbosity(verbosity: int) -> None:
    """Dynamically adjust the verbosity level at runtime.

    Useful for tests or for commands that change verbosity mid-execution.

    Args:
        verbosity: Integer verbosity level (-1, 0, 1, 2).
    """
    level = VERBOSITY_MAP.get(verbosity, logging.DEBUG)
    logging.getLogger(ROOT_LOGGER_NAME).setLevel(level)
    _apply_quiet_overrides(level)


def get_verbosity_level(verbosity: int) -> int:
    """Convert a CLI verbosity integer to a ``logging`` level constant.

    Args:
        verbosity: -1, 0, 1, or 2.

    Returns:
        A ``logging`` level (e.g. ``logging.INFO``).
    """
    return VERBOSITY_MAP.get(verbosity, logging.DEBUG)


# ── Internal helpers ─────────────────────────────────────────────────────


def _add_console_handler(
    logger: logging.Logger,
    level: int,
    stream: TextIO,
) -> None:
    """Add a stderr-stream handler with a simple format.

    Using stderr (not stdout) for logs keeps structured output on stdout
    clean when the CLI is used in pipes or scripts.
    """
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)

    if level == logging.DEBUG:
        fmt = DETAILED_FORMAT
    else:
        fmt = SIMPLE_FORMAT

    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    logger.addHandler(handler)


def _add_file_handler(
    logger: logging.Logger,
    level: int,
    log_file: str,
) -> None:
    """Add a file handler for persistent logging."""
    try:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    except (OSError, PermissionError) as exc:
        # If we cannot write the log file, warn via stderr and continue.
        logger.warning("Cannot open log file %s: %s", log_file, exc)


def _apply_quiet_overrides(active_level: int) -> None:
    """Keep known-noisy loggers at a saner minimum level during debug.

    When the root ``ajo`` logger is at DEBUG, the sub-loggers below
    are pinned to INFO to avoid overwhelming output.
    """
    if active_level == logging.DEBUG:
        for name in _QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.INFO)
