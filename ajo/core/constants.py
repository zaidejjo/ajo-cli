"""Nerd Font icons and color theme constants for the ajo-cli TUI.

This module contains only pure data — no external dependencies, no logic.
The :class:`NF` class provides Nerd Font icon codepoints for every UI element.
The :class:`Theme` class defines the cyberpunk neon color palette.

These constants are consumed by ``ajo/ui/theme.py`` for Rich/InquirerPy styling
and by UI functions throughout the codebase.
"""

from typing import Final


class NF:
    """Nerd Font icons for the professional TUI.

    Every icon constant is a single Unicode codepoint from the
    `Nerd Fonts <https://www.nerdfonts.com/>`_ icon set.  Rendering
    depends on the terminal emulator having a compatible patched font
    installed or configured.
    """

    # ------------------------------------------------------------------
    # Brand & Technology
    # ------------------------------------------------------------------
    PYTHON: Final[str] = "\ue835"  # 
    DJANGO: Final[str] = "\uf033e"  # 󰌾
    UV: Final[str] = "\uf1c4d"  # 󱑍
    RUFF: Final[str] = "\uf0617"  # 󱘗
    GIT: Final[str] = "\uf0222"  # 󰊢
    GITHUB: Final[str] = "\uf0224"  # 󰊤
    DOCKER: Final[str] = "\uf0868"  # 󰡨

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE: Final[str] = "\uf01bc"  # 󰆼
    SQLITE: Final[str] = "\uf033e"  # 󰌾
    POSTGRES: Final[str] = "\ue75e"  # 
    MYSQL: Final[str] = "\ue704"  # 

    # ------------------------------------------------------------------
    # UI Elements
    # ------------------------------------------------------------------
    ARROW_RIGHT: Final[str] = "\uf0454"  # 󰁔
    ARROW_DOWN: Final[str] = "\uf0462"  # 󰁢
    CHECK: Final[str] = "\uf012c"  # 󰄬
    CHECK_CIRCLE: Final[str] = "\uf0135"  # 󰄵
    ERROR: Final[str] = "\uf0156"  # 󰅖
    ERROR_CIRCLE: Final[str] = "\uf0158"  # 󰅘
    WARNING: Final[str] = "\uf002a"  # 󰀪
    INFO: Final[str] = "\uf0336"  # 󰌶
    BULLET: Final[str] = "\uf0142"  # 󰅂

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    ROCKET: Final[str] = "\uf044b"  # 󱐋
    GEAR: Final[str] = "\uf0493"  # 󰒓
    LOCK: Final[str] = "\uf033e"  # 󰌾
    LOCK_OPEN: Final[str] = "\uf033f"  # 󰌿
    GLOBE: Final[str] = "\uf02c9"  # 󰋉
    HEART: Final[str] = "\uf02a0"  # 󰨞
    STAR: Final[str] = "\uf0109"  # 󰄉
    STAR_FILL: Final[str] = "\uf04e5"  # 󰓥
    CLOCK: Final[str] = "\uf0150"  # 󰅐
    USER: Final[str] = "\uf0672"  # 󰙲
    USERS: Final[str] = "\uf03c5"  # 󰿅

    # ------------------------------------------------------------------
    # Dev Tools
    # ------------------------------------------------------------------
    TERMINAL: Final[str] = "\uf018d"  # 󰆍
    SERVER: Final[str] = "\uf0308"  # 󰌈
    CODE: Final[str] = "\uf0184"  # 󰡄
    EDITOR: Final[str] = "\uf02a0"  # 󰨞
    DEBUG: Final[str] = "\uf00e4"  # 󰃤
    TEST: Final[str] = "\uf0668"  # 󰙨
    SHELL: Final[str] = "\uf04de"  # 󱓞
    URL: Final[str] = "\uf030c"  # 󰌌
    CACHE: Final[str] = "\uf027a"  # 󰩺

    # ------------------------------------------------------------------
    # File System
    # ------------------------------------------------------------------
    FOLDER: Final[str] = "\uf024b"  # 󰉋
    FOLDER_OPEN: Final[str] = "\uf024c"  # 󰉌
    FILE: Final[str] = "\uf0184"  # 󰡄
    FILE_CONFIG: Final[str] = "\uf0493"  # 󰒓
    TRASH: Final[str] = "\uf027a"  # 󰩺
    SEARCH: Final[str] = "\uf0349"  # 󰍉

    # ------------------------------------------------------------------
    # Django Specific
    # ------------------------------------------------------------------
    APP: Final[str] = "\uf08c6"  # 󰣆
    MODEL: Final[str] = "\uf0924"  # 󰤤
    MIGRATION: Final[str] = "\uf03d8"  # 󰏘
    STACK: Final[str] = "\uf0318"  # 󰌘
    SETTINGS: Final[str] = "\uf0493"  # 󰒓

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    STATUS_SUCCESS: Final[str] = "\uf012c"  # 󰄬
    STATUS_ERROR: Final[str] = "\uf0156"  # 󰅖
    STATUS_WARNING: Final[str] = "\uf002a"  # 󰀪
    STATUS_INFO: Final[str] = "\uf0336"  # 󰌶
    STATUS_RUNNING: Final[str] = "\uf0764"  # 󰝤
    STATUS_STOPPED: Final[str] = "\uf015b"  # 󰅛


class Theme:
    """Cyberpunk neon colour palette.

    All values are hex RGB strings usable directly in Rich markup
    (e.g. ``"[bold #00f2fe]text[/]"``) and InquirerPy styles.
    """

    PRIMARY: Final[str] = "#00f2fe"  # Neon Cyan
    SECONDARY: Final[str] = "#4facfe"  # Electric Blue
    ACCENT: Final[str] = "#f355da"  # Neon Pink
    SUCCESS: Final[str] = "#00ffcc"  # Mint Green
    WARNING: Final[str] = "#ffb86c"  # Soft Orange
    ERROR: Final[str] = "#ff5555"  # Coral Red
    INFO: Final[str] = "#8be9fd"  # Soft Cyan
    MUTED: Final[str] = "#6272a4"  # Muted Grey
    TEXT: Final[str] = "#f8f8f2"  # Off-white
    BORDER: Final[str] = "#3a3f5e"  # Border
    BG_DARK: Final[str] = "#0a0e27"  # Dark background


# =============================================================================
# Nerd Font fallback resolution
# =============================================================================
# If the terminal does not render Nerd Font codepoints, swap every NF
# attribute with a safe Unicode / emoji fallback at import time.
# This happens once so that all consumers of NF.* see the resolved value.

try:
    from ajo.ui.capabilities import detect_nerd_font_support, get_icon_fallback

    if not detect_nerd_font_support():
        for _attr in dir(NF):
            if _attr.startswith("_"):
                continue
            _fallback = get_icon_fallback(_attr)
            if _fallback:
                setattr(NF, _attr, _fallback)
except Exception:
    pass  # Best-effort — keep Nerd Font codepoints if anything goes wrong
