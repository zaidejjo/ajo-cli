"""Nerd Font icon constants with automatic fallback for terminals without Nerd Font support.

Every icon is defined as a module-level constant using :func:`get_icon`,
which returns the Nerd Font glyph when the terminal supports it (and the user
has not opted out), or a clean ASCII/emoji-free fallback otherwise.

Usage::

    from ajo.ui.icons import ICON_ROCKET, ICON_SEARCH

    print(f"{ICON_ROCKET} Welcome to ajo")
"""

from __future__ import annotations

from ajo.ui.capabilities import has_nerd_fonts


def get_icon(nerd_codepoint: str, fallback: str) -> str:
    """Return the Nerd Font glyph or *fallback* based on terminal capabilities.

    Delegates to the same resolution logic used by ``NF.*`` constants so
    the user's ``config.json`` ``nerd_fonts`` preference is respected.
    """
    return nerd_codepoint if has_nerd_fonts() else fallback


# ── Brand & Welcome ─────────────────────────────────────────────────────
ICON_ROCKET = get_icon("\U000f04de", ">>")  # 󱓞  nf-cod-rocket
ICON_DJANGO = get_icon("\U000f033e", "Dj")  # 󰌾  (matches NF.DJANGO)

# ── Menu Actions ────────────────────────────────────────────────────────
ICON_SEARCH = get_icon("\U000f0349", "?")  # 󰍉  nf-fa-search
ICON_HEART_PULSE = get_icon("\U000f0565", "*")  # 󰕥  nf-fa-heartbeat
ICON_FILE = get_icon("\U000f0219", "~")  # 󰈙  nf-fa-file_o
ICON_UPGRADE = get_icon("\U000f03d7", "+")  # 󰏗  nf-fa-level_up
ICON_HISTORY = get_icon("\U000f1a8e", "@")  # 󱨎  nf-cod-history
ICON_TERMINAL = get_icon("\U000f030d", "$")  # 󰌍  nf-fa-terminal
ICON_EXIT = get_icon("\U000f015a", "x")  # 󰅚  nf-fa-sign_out

# ── UI Elements ─────────────────────────────────────────────────────────
ICON_BULLET = get_icon("\U000f0142", ">")  # 󰅂  (matches NF.BULLET)
ICON_ARROW = get_icon("\U000f0454", ">")  # 󰁔  (matches NF.ARROW_RIGHT)
ICON_CHECK = get_icon("\U000f012c", "ok")  # 󰄬  (matches NF.CHECK)
