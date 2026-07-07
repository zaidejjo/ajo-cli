"""Color / ANSI control for the ajo-cli.

Provides a single :func:`configure_console` entry point that returns
a ``rich.console.Console`` instance respecting (in precedence order):

1. ``--no-color`` / ``--color`` CLI flags (passed explicitly).
2. ``FORCE_COLOR`` environment variable.
3. ``NO_COLOR`` environment variable (https://no-color.org/).
4. ``CI`` environment variable (CI = true disables colours).
5. TTY detection — piped output defaults to no colour.

Usage::

    from ajo.core.color_control import configure_console

    console = configure_console(no_color=False, color="auto")
    console.print("[bold green]Hello[/]")
"""

from __future__ import annotations

import os
import sys
from typing import Any


# ── Sentinel for "not set" ─────────────────────────────────────────────────


class _Unset:
    """Sentinel class to distinguish "not provided" from ``None``."""

    _instance: _Unset | None = None

    def __new__(cls) -> _Unset:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<UNSET>"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()

# ── Environment variable names ────────────────────────────────────────────

NO_COLOR_ENV = "NO_COLOR"
FORCE_COLOR_ENV = "FORCE_COLOR"
CI_ENV = "CI"


# ── Public API ─────────────────────────────────────────────────────────────


def resolve_color_preference(
    *,
    no_color: bool | _Unset = UNSET,
    color: str | _Unset = UNSET,
) -> bool:
    """Determine whether ANSI colour codes should be emitted.

    Returns ``True`` if colours should be *enabled*, ``False`` otherwise.

    Precedence (highest to lowest):

    1. ``no_color=True`` → ``False`` (disable colours).
    2. ``color="never"`` → ``False``.
    3. ``color="always"`` → ``True``.
    4. ``FORCE_COLOR`` env var set → ``True``.
    5. ``NO_COLOR`` env var set → ``False``.
    6. ``CI`` env var set to ``"true"`` / ``"1"`` → ``False``.
    7. Default → :func:`sys.stdout.isatty()`.
    """
    # ── CLI flags (highest precedence) ────────────────────────────────

    if no_color is True:
        return False

    if isinstance(color, str) and color != "auto":
        return color == "always"

    # ── Environment variables ─────────────────────────────────────────

    force_color = os.environ.get(FORCE_COLOR_ENV, "")
    if force_color and force_color.lower() not in ("0", "false", ""):
        return True

    no_color_env = os.environ.get(NO_COLOR_ENV, "")
    if no_color_env:  # Any non-empty value disables colours per spec
        return False

    # ── CI detection ──────────────────────────────────────────────────

    ci = os.environ.get(CI_ENV, "").lower()
    if ci in ("true", "1", "yes"):
        return False

    # ── TTY detection ─────────────────────────────────────────────────

    return sys.stdout.isatty()


def configure_console(
    *,
    no_color: bool | _Unset = UNSET,
    color: str | _Unset = UNSET,
    **console_kwargs: Any,
) -> Any:
    """Build a ``rich.console.Console`` configured for the current environment.

    Args:
        no_color: Explicit ``--no-color`` flag.
        color: Explicit ``--color`` value (``"auto"``, ``"always"``, ``"never"``).
        **console_kwargs: Additional keyword arguments forwarded to
            ``rich.console.Console``.

    Returns:
        A configured ``Console`` instance.
    """
    # Lazy import so this module stays fast to import
    from rich.console import Console

    enable_color = resolve_color_preference(no_color=no_color, color=color)

    if enable_color:
        # When colour is explicitly forced, tell Rich not to auto-detect
        if color == "always":
            console_kwargs.setdefault("force_terminal", True)
            console_kwargs.setdefault("color_system", "truecolor")
    else:
        # Disable colours entirely — Rich will strip all ANSI codes
        console_kwargs.setdefault("no_color", True)
        console_kwargs.setdefault("color_system", None)
        # Also force terminal detection off when piped
        if not sys.stdout.isatty():
            console_kwargs.setdefault("force_terminal", False)

    return Console(**console_kwargs)


def supports_color() -> bool:
    """Simple boolean predicate — do we think the terminal supports colour?

    This is a convenience wrapper around :func:`resolve_color_preference`
    with no explicit overrides.
    """
    return resolve_color_preference()


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from *text*.

    Uses Rich's ``ansi.strip_ansi_codes`` if available, otherwise a
    simple regex fallback.

    Args:
        text: A string possibly containing ANSI escapes.

    Returns:
        Clean text with all ANSI sequences removed.
    """
    try:
        from rich.ansi import strip_ansi_codes

        return strip_ansi_codes(text)
    except ImportError:
        import re

        ansi_pattern = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_pattern.sub("", text)
