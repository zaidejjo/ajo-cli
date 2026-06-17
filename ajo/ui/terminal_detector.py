"""Terminal detection and capability fingerprinting.

Provides a unified ``TerminalDetector`` class that probes the runtime
environment for colour depth (TrueColor, 256, 16, mono), terminal
type (kitty, iTerm2, Windows Terminal, etc.), Unicode/Nerd Font
support, Sixel graphics, and bracketed paste.

All detection is passive — no escape-sequence probes are sent unless
``probe_osc4()`` / ``probe_osc10()`` are explicitly called; the
default path reads environment variables and terminfo only.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ColorDepth(Enum):
    """Detected colour depth of the terminal."""

    MONOCHROME = auto()
    ANSI_16 = auto()
    ANSI_256 = auto()
    TRUECOLOR = auto()


class TerminalType(Enum):
    """Known terminal emulators that we can optimise for."""

    UNKNOWN = auto()
    KITTY = auto()
    ITERM2 = auto()
    APPLE_TERMINAL = auto()
    VSCODE = auto()
    WINDOWS_TERMINAL = auto()
    GNOME_TERMINAL = auto()
    KONSOLE = auto()
    ALACRITTY = auto()
    FOOT = auto()
    TMUX = auto()
    SSH = auto()


# ── Capabilities dataclass ───────────────────────────────────────────────


@dataclass
class TerminalCapabilities:
    """Fingerprint of the current terminal's capabilities.

    All values are populated by :meth:`TerminalDetector.detect`.
    """

    color_depth: ColorDepth = ColorDepth.ANSI_256
    terminal_type: TerminalType = TerminalType.UNKNOWN
    is_tty: bool = False
    supports_unicode: bool = True
    supports_nerd_fonts: bool = False
    supports_sixel: bool = False
    supports_bracketed_paste: bool = False
    supports_hyperlink: bool = True
    supports_mouse: bool = False
    columns: int = 80
    lines: int = 24
    cursor_shape_available: bool = False
    cursor_blink_available: bool = False
    osc4_supported: bool = False  # :term OSC 4 (colour palette query)
    osc10_supported: bool = False  # :term OSC 10 (foreground colour query)
    colordepth_reason: str = ""

    # Raw env vars for debugging
    term_program: str = ""
    colorterm: str = ""
    term_env: str = ""

    # Cached Nerd Font icon map (pulled via :func:`has_nerd_fonts`)
    _nerf_font_icons: dict[str, str] = field(default_factory=dict)


# ── Detector ─────────────────────────────────────────────────────────────


class TerminalDetector:
    """Probe the runtime environment and build a :class:`TerminalCapabilities`.

    Usage::

        caps = TerminalDetector.detect()
        if caps.color_depth == ColorDepth.TRUECOLOR:
            ...
    """

    # Well-known Nerd Font icon codes (Pomicons / Powerline / Devicons)
    # Key = short name, value = Unicode code point.
    NERD_ICONS: dict[str, str] = {
        "folder": "\uf07b",
        "file": "\uf15b",
        "python": "\ue73c",
        "github": "\uf09b",
        "docker": "\uf308",
        "database": "\uf1c0",
        "settings": "\uf013",
        "terminal": "\uf120",
        "code": "\uf121",
        "warning": "\uf071",
        "check": "\uf00c",
        "times": "\uf00d",
        "arrow_right": "\uf105",
        "arrow_left": "\uf104",
        "arrow_up": "\uf106",
        "arrow_down": "\uf107",
        "search": "\uf002",
        "rocket": "\uf135",
        "plus": "\uf067",
        "cog": "\uf085",
        "trash": "\uf1f8",
        "sync": "\uf021",
        "globe": "\uf0ac",
        "server": "\uf233",
        "lock": "\uf023",
        "key": "\uf084",
        "branch": "\ue725",
        "git": "\ue702",
        "tag": "\uf02b",
        "box": "\uf466",
        "layers": "\uf5fd",
    }

    # Fallback ASCII icons (used when Nerd Fonts not available)
    FALLBACK_ICONS: dict[str, str] = {
        "folder": "📁",
        "file": "📄",
        "python": "🐍",
        "github": "🐙",
        "docker": "🐳",
        "database": "🗄️",
        "settings": "⚙️",
        "terminal": "💻",
        "code": "🔧",
        "warning": "⚠️",
        "check": "✓",
        "times": "✗",
        "arrow_right": ">",
        "arrow_left": "<",
        "arrow_up": "^",
        "arrow_down": "v",
        "search": "🔍",
        "rocket": "🚀",
        "plus": "+",
        "cog": "⚙️",
        "trash": "🗑️",
        "sync": "🔄",
        "globe": "🌐",
        "server": "🖥️",
        "lock": "🔒",
        "key": "🔑",
        "branch": "⎇",
        "git": "⎇",
        "tag": "🏷️",
        "box": "📦",
        "layers": "📚",
    }

    @classmethod
    def detect(cls) -> TerminalCapabilities:
        """Perform full terminal detection and return a capabilities object.

        This method reads environment variables and terminfo entries; it
        does **not** send escape sequences by default.
        """
        term_program = os.environ.get("TERM_PROGRAM", "")
        colorterm = os.environ.get("COLORTERM", "")
        term_env = os.environ.get("TERM", "")

        caps = TerminalCapabilities(
            is_tty=sys.stdout.isatty(),
            term_program=term_program,
            colorterm=colorterm,
            term_env=term_env,
        )

        cls._detect_color_depth(caps)
        cls._detect_terminal_type(caps)
        cls._detect_size(caps)
        cls._detect_unicode(caps)
        cls._detect_nerd_fonts(caps)
        cls._detect_sixel(caps)
        cls._detect_bracketed_paste(caps)
        cls._detect_cursor_features(caps)
        cls._detect_osc_support(caps)

        return caps

    @classmethod
    def _detect_color_depth(cls, caps: TerminalCapabilities) -> None:
        """Detect colour depth from env vars."""
        ct = caps.colorterm.lower() if caps.colorterm else ""

        if "truecolor" in ct or "24bit" in ct:
            caps.color_depth = ColorDepth.TRUECOLOR
            caps.colordepth_reason = f"COLORTERM={caps.colorterm}"
        elif caps.term_env and (
            "256" in caps.term_env
            or caps.term_env in ("xterm-256color", "screen-256color")
        ):
            caps.color_depth = ColorDepth.ANSI_256
            caps.colordepth_reason = f"TERM={caps.term_env}"
        elif caps.term_program and caps.term_program.lower() in (
            "iterm2",
            "kitty",
            "wezterm",
            "alacritty",
            "foot",
        ):
            caps.color_depth = ColorDepth.TRUECOLOR
            caps.colordepth_reason = f"TERM_PROGRAM={caps.term_program}"
        elif caps.term_env == "xterm":
            caps.color_depth = ColorDepth.ANSI_16
            caps.colordepth_reason = f"TERM={caps.term_env} (assumed 16)"
        else:
            caps.color_depth = ColorDepth.ANSI_256
            caps.colordepth_reason = "default (256)"

    @classmethod
    def _detect_terminal_type(cls, caps: TerminalCapabilities) -> None:
        """Identify the terminal emulator from env vars."""
        tp = caps.term_program.lower()

        if tp == "kitty":
            caps.terminal_type = TerminalType.KITTY
        elif tp == "iterm2":
            caps.terminal_type = TerminalType.ITERM2
        elif tp == "vscode" or "vscode" in os.environ.get("TERM", ""):
            caps.terminal_type = TerminalType.VSCODE
        elif tp == "windows-terminal" or os.name == "nt":
            caps.terminal_type = TerminalType.WINDOWS_TERMINAL
        elif tp == "alacritty":
            caps.terminal_type = TerminalType.ALACRITTY
        elif tp == "gnome-terminal" or os.environ.get("GNOME_TERMINAL_SCREEN"):
            caps.terminal_type = TerminalType.GNOME_TERMINAL
        elif tp == "konsole" or os.environ.get("KONSOLE_VERSION"):
            caps.terminal_type = TerminalType.KONSOLE
        elif tp == "foot":
            caps.terminal_type = TerminalType.FOOT
        elif os.environ.get("TMUX"):
            caps.terminal_type = TerminalType.TMUX
        elif os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT"):
            caps.terminal_type = TerminalType.SSH
        elif "apple" in os.environ.get("TERM_PROGRAM", "").lower():
            caps.terminal_type = TerminalType.APPLE_TERMINAL
        else:
            caps.terminal_type = TerminalType.UNKNOWN

    @classmethod
    def _detect_size(cls, caps: TerminalCapabilities) -> None:
        """Get terminal dimensions via ``shutil.get_terminal_size()``."""
        size = shutil.get_terminal_size()
        caps.columns = size.columns
        caps.lines = size.lines

    @classmethod
    def _detect_unicode(cls, caps: TerminalCapabilities) -> None:
        """Check whether the environment supports extended Unicode.

        Uses ``sys.stdout.encoding`` and ``LC_ALL`` / ``LANG`` heuristics.
        """
        enc = (sys.stdout.encoding or "").lower()
        if "utf" in enc or "utf8" in enc:
            caps.supports_unicode = True
            return
        locale = os.environ.get("LC_ALL", "") or os.environ.get("LANG", "")
        caps.supports_unicode = "utf" in locale.lower() or "UTF" in locale

    @classmethod
    def _detect_nerd_fonts(cls, caps: TerminalCapabilities) -> None:
        """Heuristic check for Nerd Font availability.

        We look for two things:
        1. ``NERD_FONTS`` env var (user can opt in).
        2. The font name in ``TERM`` or terminfo contains "nerd" / "nf".

        Returns ``True`` if we *believe* Nerd Fonts are available.
        """
        if os.environ.get("NERD_FONTS", "").lower() in ("1", "yes", "true", "on"):
            caps.supports_nerd_fonts = True
            return

        if "nerd" in caps.term_env.lower() or "-nf-" in caps.term_env.lower():
            caps.supports_nerd_fonts = True
            return

        # Check current font via terminfo (when available)
        try:
            result = subprocess.run(
                ["infocmp", "-1"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and (
                "nerd" in result.stdout.lower() or "nf-" in result.stdout.lower()
            ):
                caps.supports_nerd_fonts = True
                return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        caps.supports_nerd_fonts = False

    @classmethod
    def _detect_sixel(cls, caps: TerminalCapabilities) -> None:
        """Detect Sixel graphics support from env vars and terminfo."""
        if os.environ.get("SIXEL_SUPPORT", "").lower() in ("1", "yes", "true", "on"):
            caps.supports_sixel = True
            return
        sixel_env = os.environ.get("TERMINFO", "") or ""
        if "sixel" in sixel_env.lower():
            caps.supports_sixel = True
            return
        try:
            result = subprocess.run(
                ["infocmp", "-1"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and "sixel" in result.stdout:
                caps.supports_sixel = True
                return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        caps.supports_sixel = False

    @classmethod
    def _detect_bracketed_paste(cls, caps: TerminalCapabilities) -> None:
        """Check bracketed paste support (modern terminals all support it)."""
        modern_types = {
            TerminalType.KITTY,
            TerminalType.ITERM2,
            TerminalType.VSCODE,
            TerminalType.WINDOWS_TERMINAL,
            TerminalType.GNOME_TERMINAL,
            TerminalType.KONSOLE,
            TerminalType.ALACRITTY,
            TerminalType.FOOT,
        }
        caps.supports_bracketed_paste = caps.terminal_type in modern_types or bool(
            os.environ.get("TMUX")
        )

    @classmethod
    def _detect_cursor_features(cls, caps: TerminalCapabilities) -> None:
        """Detect cursor shape / blink capabilities."""
        caps.cursor_shape_available = caps.terminal_type in (
            TerminalType.KITTY,
            TerminalType.ITERM2,
            TerminalType.FOOT,
        )
        caps.cursor_blink_available = caps.terminal_type not in (
            TerminalType.UNKNOWN,
            TerminalType.SSH,
        )

    @classmethod
    def _detect_osc_support(cls, caps: TerminalCapabilities) -> None:
        """Detect OSC 4/10 (colour query) support."""
        caps.osc4_supported = caps.terminal_type in (
            TerminalType.KITTY,
            TerminalType.ITERM2,
            TerminalType.FOOT,
        )
        caps.osc10_supported = caps.terminal_type in (
            TerminalType.KITTY,
            TerminalType.ITERM2,
            TerminalType.FOOT,
            TerminalType.KONSOLE,
        )

    @classmethod
    def icon(cls, name: str, caps: TerminalCapabilities | None = None) -> str:
        """Return the appropriate icon for *name*, falling back as needed.

        Args:
            name: Icon key (e.g. ``"folder"``, ``"python"``).
            caps: Capabilities object.  If ``None``, we auto-detect now.

        Returns:
            The Nerd Font glyph if available, otherwise the emoji/ASCII fallback.
        """
        if caps is None:
            caps = cls.detect()
        if caps.supports_nerd_fonts:
            return cls.NERD_ICONS.get(name, cls.FALLBACK_ICONS.get(name, "?"))
        return cls.FALLBACK_ICONS.get(name, "?")

    @classmethod
    def select_icons(cls, name: str, caps: TerminalCapabilities | None = None) -> str:
        """Alias for :meth:`icon()` — used by theme rendering code."""
        return cls.icon(name, caps)
