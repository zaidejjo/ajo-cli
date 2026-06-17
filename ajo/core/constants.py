"""Nerd Font icons, theme palette constants, and theme variant enum for ajo-cli TUI.

This module provides:

* :class:`NF` — Nerd Font icon descriptors resolved dynamically via
  :class:`~ajo.core.config.ConfigManager` (or auto-detection as fallback).
* :func:`icon` — resolve any named icon to its best glyph.
* :func:`qmark` — centralised InquirerPy prompt prefix.
* :class:`Theme` — cyberpunk neon colour palette (hex strings).
* :class:`ThemeVariant` — enum of available visual themes.

All icon resolution is dynamic — the same accessor returns the Nerd Font
glyph or the text fallback depending on the user's saved preference.
"""

from __future__ import annotations

from enum import Enum, auto


# ═════════════════════════════════════════════════════════════════════════════
# Icon descriptor — resolves on every access
# ═════════════════════════════════════════════════════════════════════════════


class _NFIcon:
    """Descriptor that returns the correct icon glyph for the current config.

    Each attribute on :class:`NF` is an instance of this descriptor.
    On every attribute access, ``__get__`` queries
    :func:`~ajo.core.config.get_config` and returns either the Nerd Font
    codepoint or the text fallback.
    """

    __slots__ = ("_nf", "_fallback")

    def __init__(self, nf_codepoint: str, fallback: str) -> None:
        self._nf = nf_codepoint
        self._fallback = fallback

    def __get__(self, obj: object, objtype: type | None = None) -> str:
        return _resolve_icon(self._nf, self._fallback)


# ═════════════════════════════════════════════════════════════════════════════
# NF — icon constants (descriptor-backed)
# ═════════════════════════════════════════════════════════════════════════════


class NF:
    """Nerd Font icons for the professional TUI.

    Every attribute is a :class:`_NFIcon` descriptor.  Accessing
    ``NF.PYTHON`` returns either the Nerd Font glyph or a text fallback
    depending on the user's saved preference (``nerd_fonts`` in
    ``~/.config/ajo/config.json``) and terminal capabilities.

    Usage::

        print(f"{NF.PYTHON} Python")          # →  Python  or  Py Python
        glyph = icon("python")                  # same result, string-keyed
        prompt = qmark()                        # → 󰁔  or  ❯
    """

    # ------------------------------------------------------------------
    # Brand & Technology
    # ------------------------------------------------------------------
    PYTHON = _NFIcon("\ue835", "Py")  # 
    DJANGO = _NFIcon("\U000f033e", "Dj")  # 󰌾
    UV = _NFIcon("\U000f1c4d", "uv")  # 󱑍
    RUFF = _NFIcon("\U000f0617", "Rf")  # 󱘗
    GIT = _NFIcon("\U000f0222", "git")  # 󰊢
    GITHUB = _NFIcon("\U000f0224", "GH")  # 󰊤
    DOCKER = _NFIcon("\U000f0868", "Dk")  # 󰡨

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE = _NFIcon("\U000f01bc", "DB")  # 󰆼
    SQLITE = _NFIcon("\U000f033e", "SQLite")  # 󰌾
    POSTGRES = _NFIcon("\ue75e", "PG")  # 
    MYSQL = _NFIcon("\ue704", "MySQL")  # 

    # ------------------------------------------------------------------
    # UI Elements
    # ------------------------------------------------------------------
    ARROW_RIGHT = _NFIcon("\U000f0454", "\u276f")  # 󰁔 / ❯
    ARROW_DOWN = _NFIcon("\U000f0462", "\u2193")  # 󰁢 / ↓
    CHECK = _NFIcon("\U000f012c", "\u2714")  # 󰄬 / ✔
    CHECK_CIRCLE = _NFIcon("\U000f0135", "\u2714")  # 󰄵 / ✔
    ERROR = _NFIcon("\U000f0156", "\u2716")  # 󰅖 / ✖
    ERROR_CIRCLE = _NFIcon("\U000f0158", "\u2716")  # 󰅘 / ✖
    WARNING = _NFIcon("\U000f002a", "\u25b2")  # 󰀪 / ▲
    INFO = _NFIcon("\U000f0336", "\u2139")  # 󰌶 / ℹ
    BULLET = _NFIcon("\U000f0142", "\u276f")  # 󰅂 / ❯
    PLUS = _NFIcon("\uf067", "+")  # + / +

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    ROCKET = _NFIcon("\U000f044b", "\U0001f680")  # 󱐋 / 🚀
    GEAR = _NFIcon("\U000f0493", "\u2699")  # 󰒓 / ⚙
    LOCK = _NFIcon("\U000f033e", "\U0001f512")  # 󰌾 / 🔒
    LOCK_OPEN = _NFIcon("\U000f033f", "\U0001f513")  # 󰌿 / 🔓
    GLOBE = _NFIcon("\U000f02c9", "\U0001f310")  # 󰋉 / 🌐
    HEART = _NFIcon("\U000f02a0", "\u2764")  # 󰨞 / ❤
    STAR = _NFIcon("\U000f0109", "\u2606")  # 󰄉 / ☆
    STAR_FILL = _NFIcon("\U000f04e5", "\u2605")  # 󰓥 / ★
    CLOCK = _NFIcon("\U000f0150", "\u23f1")  # 󰅐 / ⏱
    USER = _NFIcon("\U000f0672", "\U0001f464")  # 󰙲 / 👤
    USERS = _NFIcon("\U000f03c5", "\U0001f465")  # 󰿅 / 👥

    # ------------------------------------------------------------------
    # Dev Tools
    # ------------------------------------------------------------------
    TERMINAL = _NFIcon("\U000f018d", "$")  # 󰆍 / $
    SERVER = _NFIcon("\U000f0308", "Srv")  # 󰌈
    CODE = _NFIcon("\U000f0184", "</>")  # 󰡄
    EDITOR = _NFIcon("\U000f02a0", "Ed")  # 󰨞
    DEBUG = _NFIcon("\U000f00e4", "Dbg")  # 󰃤
    TEST = _NFIcon("\U000f0668", "Tst")  # 󰙨
    SHELL = _NFIcon("\U000f04de", "sh")  # 󱓞
    URL = _NFIcon("\U000f030c", "\U0001f517")  # 󰌌 / 🔗
    CACHE = _NFIcon("\U000f027a", "Cch")  # 󰩺

    # ------------------------------------------------------------------
    # File System
    # ------------------------------------------------------------------
    FOLDER = _NFIcon("\U000f024b", "\U0001f4c1")  # 󰉋 / 📁
    FOLDER_OPEN = _NFIcon("\U000f024c", "\U0001f4c2")  # 󰉌 / 📂
    FILE = _NFIcon("\U000f0184", "\U0001f4c4")  # 󰡄 / 📄
    FILE_CONFIG = _NFIcon("\U000f0493", "\u2699")  # 󰒓 / ⚙
    TRASH = _NFIcon("\U000f027a", "\U0001f5d1")  # 󰩺 / 🗑
    SEARCH = _NFIcon("\U000f0349", "\U0001f50d")  # 󰍉 / 🔍

    # ------------------------------------------------------------------
    # Django Specific
    # ------------------------------------------------------------------
    APP = _NFIcon("\U000f08c6", "App")  # 󰣆
    MODEL = _NFIcon("\U000f0924", "Md")  # 󰤤
    MIGRATION = _NFIcon("\U000f03d8", "Mig")  # 󰏘
    STACK = _NFIcon("\U000f0318", "Stack")  # 󰌘
    SETTINGS = _NFIcon("\U000f0493", "Cfg")  # 󰒓

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    STATUS_SUCCESS = _NFIcon("\U000f012c", "\u2714")  # 󰄬 / ✔
    STATUS_ERROR = _NFIcon("\U000f0156", "\u2716")  # 󰅖 / ✖
    STATUS_WARNING = _NFIcon("\U000f002a", "\u25b2")  # 󰀪 / ▲
    STATUS_INFO = _NFIcon("\U000f0336", "\u2139")  # 󰌶 / ℹ
    STATUS_RUNNING = _NFIcon("\U000f0764", "\u25b6")  # 󰝤 / ▶
    STATUS_STOPPED = _NFIcon("\U000f015b", "\u25a0")  # 󰅛 / ■


# ═════════════════════════════════════════════════════════════════════════════
# Canonical string-keyed icon map
# ═════════════════════════════════════════════════════════════════════════════

ICON_MAP: dict[str, tuple[str, str]] = {
    # Brand
    "python": ("\ue835", "Py"),
    "django": ("\U000f033e", "Dj"),
    "uv": ("\U000f1c4d", "uv"),
    "ruff": ("\U000f0617", "Rf"),
    "git": ("\U000f0222", "git"),
    "github": ("\U000f0224", "GH"),
    "docker": ("\U000f0868", "Dk"),
    # Database
    "database": ("\U000f01bc", "DB"),
    "sqlite": ("\U000f033e", "SQLite"),
    "postgres": ("\ue75e", "PG"),
    "mysql": ("\ue704", "MySQL"),
    # UI Elements
    "arrow_right": ("\U000f0454", "\u276f"),  # ❯
    "arrow_down": ("\U000f0462", "\u2193"),  # ↓
    "check": ("\U000f012c", "\u2714"),  # ✔
    "check_circle": ("\U000f0135", "\u2714"),  # ✔
    "error": ("\U000f0156", "\u2716"),  # ✖
    "error_circle": ("\U000f0158", "\u2716"),  # ✖
    "warning": ("\U000f002a", "\u25b2"),  # ▲
    "info": ("\U000f0336", "\u2139"),  # ℹ
    "bullet": ("\U000f0142", "\u276f"),  # ❯
    "plus": ("\uf067", "+"),
    # Actions
    "rocket": ("\U000f044b", "\U0001f680"),
    "gear": ("\U000f0493", "\u2699"),
    "lock": ("\U000f033e", "\U0001f512"),
    "globe": ("\U000f02c9", "\U0001f310"),
    "user": ("\U000f0672", "\U0001f464"),
    # Dev Tools
    "terminal": ("\U000f018d", "$"),
    "server": ("\U000f0308", "Srv"),
    "code": ("\U000f0184", "</>"),
    "test": ("\U000f0668", "Tst"),
    "cache": ("\U000f027a", "Cch"),
    "url": ("\U000f030c", "\U0001f517"),
    # File System
    "folder": ("\U000f024b", "\U0001f4c1"),
    "file": ("\U000f0184", "\U0001f4c4"),
    "search": ("\U000f0349", "\U0001f50d"),
    # Django
    "app": ("\U000f08c6", "App"),
    "model": ("\U000f0924", "Md"),
    "migration": ("\U000f03d8", "Mig"),
    # Status
    "status_success": ("\U000f012c", "\u2714"),
    "status_error": ("\U000f0156", "\u2716"),
    "status_warning": ("\U000f002a", "\u25b2"),
    "status_info": ("\U000f0336", "\u2139"),
    "status_running": ("\U000f0764", "\u25b6"),
    "status_stopped": ("\U000f015b", "\u25a0"),
}


# ═════════════════════════════════════════════════════════════════════════════
# Resolution helpers
# ═════════════════════════════════════════════════════════════════════════════


def _resolve_icon(nf_codepoint: str, fallback: str) -> str:
    """Core resolution: return *nf_codepoint* or *fallback* based on config.

    Precedence:
    1. Config-manager preference (``nerd_fonts`` key in ``config.json``).
    2. Auto-detection via :func:`~ajo.ui.capabilities.has_nerd_fonts`.
    3. *fallback* as the ultimate default.
    """
    try:
        from ajo.core.config import get_config

        config = get_config()
        if config is not None:
            pref = config.get("nerd_fonts")
            if pref is True:
                return nf_codepoint
            if pref is False:
                return fallback
        # No config preference yet — fall back to auto-detection
        from ajo.ui.capabilities import has_nerd_fonts

        if has_nerd_fonts():
            return nf_codepoint
    except Exception:
        pass
    return fallback


def icon(key: str) -> str:
    """Return the best glyph for *key* given current config and terminal caps.

    Args:
        key: A key from :data:`ICON_MAP` (e.g. ``"python"``, ``"folder"``).

    Returns:
        The Nerd Font codepoint if enabled, otherwise the text fallback.
        Returns ``"?"`` for unknown keys.
    """
    entry = ICON_MAP.get(key)
    if entry is None:
        return "?"
    return _resolve_icon(entry[0], entry[1])


def qmark() -> str:
    """Return the prompt prefix character for InquirerPy prompts.

    Returns the Nerd Font arrow (``󰁔``) or the fallback chevron (``❯``)
    depending on the user's ``nerd_fonts`` preference.
    """
    return icon("arrow_right")


# ═════════════════════════════════════════════════════════════════════════════
# ThemeVariant
# ═════════════════════════════════════════════════════════════════════════════


class ThemeVariant(Enum):
    """Available visual themes for the ajo-cli TUI."""

    CYBERPUNK = auto()
    DRACULA = auto()
    MONOCHROMATIC = auto()

    @classmethod
    def from_string(cls, value: str) -> ThemeVariant:
        """Parse a theme name (case-insensitive)."""
        mapping = {
            "cyberpunk": cls.CYBERPUNK,
            "dracula": cls.DRACULA,
            "monochromatic": cls.MONOCHROMATIC,
            "mono": cls.MONOCHROMATIC,
        }
        return mapping.get(value.strip().lower(), cls.CYBERPUNK)


# ═════════════════════════════════════════════════════════════════════════════
# Theme — cyberpunk colour palette
# ═════════════════════════════════════════════════════════════════════════════


class Theme:
    """Cyberpunk neon colour palette.

    All values are hex RGB strings usable directly in Rich markup
    (e.g. ``"[bold #00f2fe]text[/]"``) and InquirerPy styles.
    """

    PRIMARY: str = "#00f2fe"  # Neon Cyan
    SECONDARY: str = "#4facfe"  # Electric Blue
    ACCENT: str = "#f355da"  # Neon Pink
    SUCCESS: str = "#00ffcc"  # Mint Green
    WARNING: str = "#ffb86c"  # Soft Orange
    ERROR: str = "#ff5555"  # Coral Red
    INFO: str = "#8be9fd"  # Soft Cyan
    MUTED: str = "#6272a4"  # Muted Grey
    TEXT: str = "#f8f8f2"  # Off-white
    BORDER: str = "#3a3f5e"  # Border
    BG_DARK: str = "#0a0e27"  # Dark background
