"""Graceful signal handling for Ctrl+C and SIGTERM.

Provides a global :data:`_interrupted` flag and a :func:`register_rollback_handler`
mechanism so that long-running operations (scaffold, subprocess, interactive
prompts) can be safely interrupted without leaving half-written files.

Usage::

    from ajo.core.signals import install_signal_handlers, register_rollback_handler

    install_signal_handlers()
    register_rollback_handler(lambda: cleanup())

    # ... long operation ...
    # Ctrl+C → runs cleanup, exits 130

    # After the operation, clear the handler:
    register_rollback_handler(None)
"""

from __future__ import annotations

import signal
import sys
from typing import Any, Callable


#: Global flag set by the signal handler.  Long-running loops can poll this
#: to decide whether to abort early.
interrupted: bool = False

#: The registered rollback callable (or ``None``).
_rollback_handler: Callable[[], Any] | None = None


# ── Public API ─────────────────────────────────────────────────────────────


def register_rollback_handler(fn: Callable[[], Any] | None) -> None:
    """Register a zero-argument callable to run on SIGINT / SIGTERM.

    Pass ``None`` to clear the handler after the guarded operation
    completes.

    Args:
        fn: A callable invoked when a termination signal is received.
            It is called *after* the signal fires — it should perform
            cleanup such as temporary-file removal, rollback, or progress
            bar termination.
    """
    global _rollback_handler
    _rollback_handler = fn


def install_signal_handlers() -> None:
    """Install global handlers for ``SIGINT`` and ``SIGTERM``.

    The handler:

    1. Sets the :data:`interrupted` flag to ``True``.
    2. Prints a newline (to clean up the prompt line).
    3. Calls the registered rollback handler (if any).
    4. Exits with code 130 (POSIX convention for Ctrl+C).

    This function is idempotent — calling it multiple times is safe.
    It is intentionally **not** called at import time; callers must
    invoke it explicitly.
    """
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


# ── Internal ────────────────────────────────────────────────────────────────


def _signal_handler(signum: int, frame: object) -> None:  # noqa: ARG001
    """Handle SIGINT / SIGTERM: set flag, run rollback, exit 130."""
    global interrupted, _rollback_handler
    interrupted = True

    # Print newline to break whatever prompt / progress was on screen
    sys.stderr.write("\n")
    sys.stderr.flush()

    handler = _rollback_handler
    if handler is not None:
        try:
            handler()
        except Exception:
            # Best-effort: don't let a rollback failure mask the interrupt
            pass

    sys.exit(130)
