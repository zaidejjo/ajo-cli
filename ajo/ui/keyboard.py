"""Keyboard-driven navigation and zone layout management.

Provides:
- :class:`KeyBinding` — describes a single keyboard shortcut.
- :class:`KeyEvent` — well-known key identifiers.
- :class:`KeyboardManager` — register / dispatch key events.
- :class:`ZoneManager` — 6-zone layout (header, sidebar, main, status,
  action, footer) with resize handling.
"""

from __future__ import annotations

import dataclasses
import signal
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ── Key identifiers ──────────────────────────────────────────────────────


class KeyEvent(Enum):
    """Symbolic key identifiers used for binding dispatch."""

    # Navigation
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    TAB = auto()
    SHIFT_TAB = auto()
    ENTER = auto()
    ESCAPE = auto()
    SPACE = auto()

    # Actions
    DELETE = auto()
    BACKSPACE = auto()
    HOME = auto()
    END = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()

    # Function keys
    F1 = auto()
    F2 = auto()
    F3 = auto()
    F4 = auto()
    F5 = auto()
    F6 = auto()
    F7 = auto()
    F8 = auto()
    F9 = auto()
    F10 = auto()
    F11 = auto()
    F12 = auto()

    # Modifier combos
    CTRL_A = auto()
    CTRL_C = auto()
    CTRL_D = auto()
    CTRL_E = auto()
    CTRL_F = auto()
    CTRL_G = auto()
    CTRL_L = auto()
    CTRL_N = auto()
    CTRL_P = auto()
    CTRL_Q = auto()
    CTRL_R = auto()
    CTRL_S = auto()
    CTRL_T = auto()
    CTRL_U = auto()
    CTRL_V = auto()
    CTRL_W = auto()
    CTRL_X = auto()
    CTRL_Y = auto()
    CTRL_Z = auto()

    # Characters (for search / filter typing)
    CHAR = auto()

    # Special
    UNKNOWN = auto()


# ── KeyBinding ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KeyBinding:
    """Describes a single keyboard binding.

    Attributes:
        key: The :class:`KeyEvent` that triggers this binding.
        description: Human-readable label (shown in action bar).
        handler: Async callable ``(event) -> None``.
        zone: Optional zone name that this binding applies to
            (e.g. ``"sidebar"``, ``"main"``).  ``None`` means global.
        context: Optional context string for context-sensitive bindings
            (e.g. ``"search_active"``).
    """

    key: KeyEvent
    description: str
    handler: Callable[[KeyEvent], Any]
    zone: str | None = None
    context: str | None = None


# ── KeyboardManager ──────────────────────────────────────────────────────


class KeyboardManager:
    """Register and dispatch keyboard events.

    Usage::

        km = KeyboardManager()
        km.register(KeyEvent.CTRL_Q, "Quit", lambda e: sys.exit(0))
        km.register(KeyEvent.UP, "Move up", my_up_handler, zone="sidebar")
        await km.dispatch(KeyEvent.UP)  # dispatches to all matching handlers
    """

    def __init__(self) -> None:
        self._bindings: list[KeyBinding] = []
        self._context: str = ""

    # ── Registration ──────────────────────────────────────────────────

    def register(
        self,
        key: KeyEvent,
        description: str,
        handler: Callable[[KeyEvent], Any],
        *,
        zone: str | None = None,
        context: str | None = None,
    ) -> KeyBinding:
        """Register a new key binding.

        Args:
            key: The :class:`KeyEvent` to bind.
            description: Human-readable label.
            handler: Callable that accepts a :class:`KeyEvent`.
            zone: Optional zone scoping.
            context: Optional context scoping.

        Returns:
            The created :class:`KeyBinding`.
        """
        binding = KeyBinding(
            key=key,
            description=description,
            handler=handler,
            zone=zone,
            context=context,
        )
        self._bindings.append(binding)
        return binding

    def unregister(self, binding: KeyBinding) -> None:
        """Remove a previously registered binding."""
        self._bindings.remove(binding)

    def clear_zone(self, zone: str) -> None:
        """Remove all bindings for a given zone."""
        self._bindings = [b for b in self._bindings if b.zone != zone]

    def set_context(self, context: str) -> None:
        """Set the current context for context-sensitive dispatch."""
        self._context = context

    # ── Dispatch ──────────────────────────────────────────────────────

    async def dispatch(self, event: KeyEvent) -> bool:
        """Dispatch a :class:`KeyEvent` to all matching handlers.

        Args:
            event: The key event to dispatch.

        Returns:
            ``True`` if at least one handler was called, ``False`` otherwise.
        """
        handled = False
        for binding in self._bindings:
            if binding.key != event:
                continue
            if binding.context and binding.context != self._context:
                continue
            result = binding.handler(event)
            if result is not None:
                # Support both sync and async handlers
                if hasattr(result, "__await__"):
                    await result
            handled = True
        return handled

    # ── Queries ───────────────────────────────────────────────────────

    def get_bindings_for_zone(self, zone: str) -> list[KeyBinding]:
        """Return all bindings scoped to *zone* (plus global ones)."""
        return [b for b in self._bindings if b.zone is None or b.zone == zone]

    def get_current_shortcuts(self) -> list[KeyBinding]:
        """Return all bindings active in the current context."""
        return [
            b for b in self._bindings if b.context is None or b.context == self._context
        ]


# ── Zone identifiers ─────────────────────────────────────────────────────


class Zone(Enum):
    """Named layout zones in the 6-zone TUI."""

    HEADER = auto()
    SIDEBAR = auto()
    MAIN = auto()
    STATUS_BAR = auto()
    ACTION_BAR = auto()
    FOOTER = auto()


# ── Zone geometry ────────────────────────────────────────────────────────


@dataclass
class ZoneGeometry:
    """Screen-space geometry for a single zone."""

    top: int = 0
    left: int = 0
    width: int = 80
    height: int = 1
    visible: bool = True


# ── ZoneManager ──────────────────────────────────────────────────────────


class ZoneManager:
    """Manages the 6-zone screen layout with auto-resize handling.

    Layout::

        ┌──────────────────────────────────────────────┐
        │  HEADER (1 line)              ║              │
        ├──────────────┬───────────────────────────────┤
        │              │                               │
        │   SIDEBAR    │         MAIN                  │
        │  (30% width) │       (70% width)             │
        │              │                               │
        │              │                               │
        ├──────────────┴───────────────────────────────┤
        │  STATUS_BAR (1 line)                         │
        ├──────────────────────────────────────────────┤
        │  ACTION_BAR (1 line)                         │
        ├──────────────────────────────────────────────┤
        │  FOOTER (1 line)                             │
        └──────────────────────────────────────────────┘
    """

    def __init__(self) -> None:
        self.total_cols: int = 80
        self.total_rows: int = 24
        self.sidebar_width_ratio: float = 0.30
        self._zones: dict[Zone, ZoneGeometry] = {zone: ZoneGeometry() for zone in Zone}
        self._resize_handlers: list[Callable[[int, int], None]] = []
        self._setup_signal()

    def _setup_signal(self) -> None:
        """Register SIGWINCH handler for terminal resize."""
        try:
            signal.signal(signal.SIGWINCH, self._on_sigwinch)
        except (AttributeError, ValueError):
            pass  # Not on Unix or not in main thread

    def _on_sigwinch(self, _sig: int, _frame: Any) -> None:
        """Recalculate layout on terminal resize."""
        import shutil

        size = shutil.get_terminal_size()
        self.resize(size.columns, size.lines)

    def on_resize(self, handler: Callable[[int, int], None]) -> None:
        """Register a callback that fires on terminal resize."""
        self._resize_handlers.append(handler)

    def resize(self, cols: int, rows: int) -> None:
        """Recalculate all zone geometries for *cols* × *rows*.

        Args:
            cols: New terminal width in columns.
            rows: New terminal height in rows.
        """
        self.total_cols = cols
        self.total_rows = rows

        # Fixed row allocations
        header_h = min(3, max(1, rows // 10))
        status_h = 1
        action_h = 1
        footer_h = 1
        sidebar_w = max(20, int(cols * self.sidebar_width_ratio))
        main_w = cols - sidebar_w
        content_h = rows - header_h - status_h - action_h - footer_h

        if content_h < 1:
            content_h = 1

        self._zones[Zone.HEADER] = ZoneGeometry(
            top=0,
            left=0,
            width=cols,
            height=header_h,
        )
        self._zones[Zone.SIDEBAR] = ZoneGeometry(
            top=header_h,
            left=0,
            width=sidebar_w,
            height=content_h,
        )
        self._zones[Zone.MAIN] = ZoneGeometry(
            top=header_h,
            left=sidebar_w,
            width=main_w,
            height=content_h,
        )
        self._zones[Zone.STATUS_BAR] = ZoneGeometry(
            top=header_h + content_h,
            left=0,
            width=cols,
            height=status_h,
        )
        self._zones[Zone.ACTION_BAR] = ZoneGeometry(
            top=header_h + content_h + status_h,
            left=0,
            width=cols,
            height=action_h,
        )
        self._zones[Zone.FOOTER] = ZoneGeometry(
            top=header_h + content_h + status_h + action_h,
            left=0,
            width=cols,
            height=footer_h,
        )

        for handler in self._resize_handlers:
            handler(cols, rows)

    def get_zone(self, zone: Zone) -> ZoneGeometry:
        """Return the geometry for a given zone."""
        return self._zones[zone]

    def set_sidebar_visible(self, visible: bool) -> None:
        """Show or hide the sidebar, redistributing width to main."""
        sidebar = self._zones[Zone.SIDEBAR]
        sidebar.visible = visible
        if not visible:
            self._zones[Zone.MAIN].left = 0
            self._zones[Zone.MAIN].width = self.total_cols
        else:
            sidebar_w = max(20, int(self.total_cols * self.sidebar_width_ratio))
            sidebar.width = sidebar_w
            self._zones[Zone.MAIN].left = sidebar_w
            self._zones[Zone.MAIN].width = self.total_cols - sidebar_w
