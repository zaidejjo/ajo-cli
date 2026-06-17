"""Terminal capability detection — unified wrapper around ``TerminalDetector``.

This module re-exports the core detection logic from
:mod:`ajo.ui.terminal_detector` and maintains the backward-compatible
``ICON_FALLBACK_MAP`` for older code paths.

Usage::

    from ajo.ui.capabilities import has_nerd_fonts, icon, ColorDepth
"""

from __future__ import annotations

from typing import Any

from ajo.ui.terminal_detector import (
    ColorDepth,
    TerminalCapabilities,
    TerminalDetector,
    TerminalType,
)

# ── Backward-compatible icon map ─────────────────────────────────────────
# Code that still imports ICON_FALLBACK_MAP directly will get these.

ICON_FALLBACK_MAP: dict[str, str] = dict(TerminalDetector.FALLBACK_ICONS)

# ── Cached singleton capabilities ────────────────────────────────────────
# Detected once on first access, then reused.

_cached_caps: TerminalCapabilities | None = None


def _get_caps() -> TerminalCapabilities:
    """Return the cached :class:`TerminalCapabilities`, detecting if needed."""
    global _cached_caps
    if _cached_caps is None:
        _cached_caps = TerminalDetector.detect()
    return _cached_caps


# ── Public API ───────────────────────────────────────────────────────────


def detect_color_depth() -> ColorDepth:
    """Return the detected :class:`ColorDepth`."""
    return _get_caps().color_depth


def detect_terminal_type() -> TerminalType:
    """Return the detected :class:`TerminalType`."""
    return _get_caps().terminal_type


def has_nerd_fonts() -> bool:
    """Return ``True`` if Nerd Fonts are available.

    Checks the persistent config first (highest precedence), then falls
    back to auto-detection via :class:`~ajo.ui.terminal_detector.TerminalDetector`.
    """
    try:
        from ajo.core.config import get_config

        config = get_config()
        if config is not None:
            pref = config.get("nerd_fonts")
            if pref is True:
                return True
            if pref is False:
                return False
    except Exception:
        pass
    return _get_caps().supports_nerd_fonts


def has_true_color() -> bool:
    """Return ``True`` if the terminal supports TrueColor (24-bit)."""
    return _get_caps().color_depth == ColorDepth.TRUECOLOR


def terminal_columns() -> int:
    """Return the current terminal width (columns)."""
    return _get_caps().columns


def terminal_lines() -> int:
    """Return the current terminal height (lines)."""
    return _get_caps().lines


def icon(name: str, *, fallback: str | None = None) -> str:
    """Return the best icon for *name* given current terminal capabilities.

    Args:
        name: The icon key (e.g. ``"folder"``, ``"python"``, ``"warning"``).
        fallback: Optional override string if no icon is found.

    Returns:
        A Nerd Font glyph if available, otherwise an emoji fallback.
    """
    result = TerminalDetector.icon(name, _get_caps())
    if result == "?" and fallback is not None:
        return fallback
    return result


def select_icons(name: str) -> str:
    """Alias for :func:`icon()` used by theme rendering."""
    return icon(name)


def get_full_report() -> dict[str, Any]:
    """Return a human-readable dict of all detected capabilities."""
    caps = _get_caps()
    return {
        "Color Depth": caps.color_depth.name,
        "Terminal Type": caps.terminal_type.name,
        "TTY": caps.is_tty,
        "Unicode": caps.supports_unicode,
        "Nerd Fonts": caps.supports_nerd_fonts,
        "Sixel": caps.supports_sixel,
        "Bracketed Paste": caps.supports_bracketed_paste,
        "Hyperlinks": caps.supports_hyperlink,
        "Columns": caps.columns,
        "Lines": caps.lines,
        "Cursor Shape": caps.cursor_shape_available,
        "OSC 4": caps.osc4_supported,
        "OSC 10": caps.osc10_supported,
        "Reason": caps.colordepth_reason,
    }
