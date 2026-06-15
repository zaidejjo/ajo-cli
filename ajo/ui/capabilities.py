"""Terminal capability detection for icon fallback.

Detects whether the terminal supports Nerd Font icon codepoints and
provides a fallback mapping to safe Unicode / emoji alternatives.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Final

# ── Nerd Font fallback map ─────────────────────────────────────────────
# Maps NF class attribute names to safe fallback characters (emoji/ASCII).
# These are used when the terminal does not support Nerd Font patched
# fonts.

ICON_FALLBACK_MAP: Final[dict[str, str]] = {
    # Brand & Technology
    "PYTHON": "\U0001f40d",  # 🐍
    "DJANGO": "\U0001f3af",  # 🎯
    "UV": "\U0001f4e6",  # 📦
    "RUFF": "\U0001f50d",  # 🔍
    "GIT": "\U0001f500",  # 🔀
    "GITHUB": "\U0001f419",  # 🐙
    "DOCKER": "\U0001f433",  # 🐳
    # Database
    "DATABASE": "\U0001f5c4\ufe0f",  # 🗄️
    "SQLITE": "\U0001f4be",  # 💾
    "POSTGRES": "\U0001f418",  # 🐘
    "MYSQL": "\U0001f42c",  # 🐬
    # UI Elements
    "ARROW_RIGHT": "\u25b6",  # ▶
    "ARROW_DOWN": "\u25bc",  # ▼
    "CHECK": "\u2713",  # ✓
    "CHECK_CIRCLE": "\u2714",  # ✔
    "ERROR": "\u2717",  # ✗
    "ERROR_CIRCLE": "\u2718",  # ✘
    "WARNING": "\u26a0",  # ⚠
    "INFO": "\u2139",  # ℹ
    "BULLET": "\u2022",  # •
    # Actions
    "ROCKET": "\U0001f680",  # 🚀
    "GEAR": "\u2699",  # ⚙
    "LOCK": "\U0001f512",  # 🔒
    "LOCK_OPEN": "\U0001f513",  # 🔓
    "GLOBE": "\U0001f310",  # 🌐
    "HEART": "\u2665",  # ♥
    "STAR": "\u2605",  # ★
    "STAR_FILL": "\u2b50",  # ⭐
    "CLOCK": "\u23f1",  # ⏱
    "USER": "\U0001f464",  # 👤
    "USERS": "\U0001f465",  # 👥
    # Dev Tools
    "TERMINAL": "\U0001f4bb",  # 💻
    "SERVER": "\U0001f5a5",  # 🖥
    "CODE": "\u2328",  # ⌨
    "EDITOR": "\u270f\ufe0f",  # ✏️
    "DEBUG": "\U0001f41b",  # 🐛
    "TEST": "\U0001f9ea",  # 🧪
    "SHELL": "\u2318",  # ⌘
    "URL": "\U0001f517",  # 🔗
    "CACHE": "\u26a1",  # ⚡
    # File System
    "FOLDER": "\U0001f4c1",  # 📁
    "FOLDER_OPEN": "\U0001f4c2",  # 📂
    "FILE": "\U0001f4c4",  # 📄
    "FILE_CONFIG": "\u2699\ufe0f",  # ⚙️
    "TRASH": "\U0001f5d1",  # 🗑
    "SEARCH": "\U0001f50e",  # 🔎
    # Django Specific
    "APP": "\U0001f4f1",  # 📱
    "MODEL": "\U0001f4cb",  # 📋
    "MIGRATION": "\U0001f4e4",  # 📤
    "STACK": "\U0001f4da",  # 📚
    "SETTINGS": "\U0001f527",  # 🔧
    # Status
    "STATUS_SUCCESS": "\u2714",  # ✔
    "STATUS_ERROR": "\u2718",  # ✘
    "STATUS_WARNING": "\u26a0",  # ⚠
    "STATUS_INFO": "\u2139",  # ℹ
    "STATUS_RUNNING": "\U0001f504",  # 🔄
    "STATUS_STOPPED": "\u23f9",  # ⏹
}


# ── Detection ─────────────────────────────────────────────────────────


def _check_terminal_env() -> bool:
    """Check environment variables for Nerd Font support.

    Known Nerd Font-capable terminals are detected via environment
    variables like ``TERM_PROGRAM``, ``TERM``, and ``XTERM_VERSION``.
    """
    term_program = os.environ.get("TERM_PROGRAM", "")
    term = os.environ.get("TERM", "")
    alacritty_version = os.environ.get("ALACRITTY_VERSION", "")
    vte_version = os.environ.get("VTE_VERSION", "")

    # Known good terminals
    if term_program in ("iTerm.app", "Hyper", "Tabby", "WarpTerminal", "WezTerm"):
        return True
    if alacritty_version:
        return True
    if "wezterm" in term.lower():
        return True
    if "kitty" in term.lower():
        return True
    if "foot" in term.lower():
        return True

    # VS Code's integrated terminal — supports Nerd Fonts when configured
    if term_program == "vscode" and vte_version:
        return True

    return False


def _check_nerd_font_rendering() -> bool:
    """Check if the terminal likely supports Nerd Fonts.

    Uses environment heuristics; on non-TTY or CI output falls back
    to ``False``.
    """
    if not sys.stdout.isatty():
        return False

    # Try a quick tput check; if it fails, fall back to env heuristic
    try:
        result = subprocess.run(
            ["tput", "cols"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return _check_terminal_env()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _check_terminal_env()

    return _check_terminal_env()


def detect_nerd_font_support() -> bool:
    """Determine whether the terminal supports Nerd Font icons.

    Returns ``True`` if the terminal is known to support Nerd Fonts
    (iTerm2, Kitty, Alacritty, WezTerm, etc.) and stdout is a TTY.

    The result is memoized so repeated calls are cheap.
    """
    cache_attr = "_cached"
    if not hasattr(detect_nerd_font_support, cache_attr):
        setattr(detect_nerd_font_support, cache_attr, _check_nerd_font_rendering())
    return getattr(detect_nerd_font_support, cache_attr)  # type: ignore[return-value]


def get_icon_fallback(attr_name: str, default: str = "?") -> str:
    """Return the fallback character for a given NF attribute name.

    Args:
        attr_name: The attribute name from the :class:`NF` class
            (e.g. ``"PYTHON"``, ``"DATABASE"``).
        default: Character to return if no fallback is known.

    Returns:
        A fallback character string.
    """
    return ICON_FALLBACK_MAP.get(attr_name, default)
