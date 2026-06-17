"""Rich and InquirerPy style configuration for the ajo-cli TUI.

Provides the :class:`ThemeEngine` singleton with three built-in palettes
(Cyberpunk, Dracula, Monochromatic), dynamic colour-depth adaptation, and
the :class:`FileTreePreview` class for rendering scaffold-file previews.

Every public name from the legacy single-theme module is re-exported here
so that all existing imports continue to work.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ajo.core.constants import Theme, ThemeVariant, icon


# =============================================================================
# ThemePalette — a single colour palette
# =============================================================================


@dataclass(frozen=True)
class ThemePalette:
    """A named colour palette with all TUI colour tokens."""

    variant: ThemeVariant
    name: str
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    error: str
    info: str
    muted: str
    text: str
    border: str
    bg_dark: str
    bg_light: str = ""
    surface: str = ""
    selection_bg: str = ""

    # ── Optional per-variant overrides for InquirerPy ────────────────
    inquirer_overrides: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, str]:
        """Return palette as a flat dict for programmatic access."""
        return {
            f.name: getattr(self, f.name)
            for f in dataclasses.fields(self)
            if isinstance(getattr(self, f.name), str) and f.name != "name"
        }


# ── Three built-in palettes ─────────────────────────────────────────────


CYBERPUNK_PALETTE = ThemePalette(
    variant=ThemeVariant.CYBERPUNK,
    name="Cyberpunk",
    primary="#00f2fe",
    secondary="#4facfe",
    accent="#f355da",
    success="#00ffcc",
    warning="#ffb86c",
    error="#ff5555",
    info="#8be9fd",
    muted="#6272a4",
    text="#f8f8f2",
    border="#3a3f5e",
    bg_dark="#0a0e27",
    bg_light="#1e2240",
    surface="#151935",
    selection_bg="#2a2f55",
    inquirer_overrides={},
)

DRACULA_PALETTE = ThemePalette(
    variant=ThemeVariant.DRACULA,
    name="Dracula",
    primary="#bd93f9",
    secondary="#ff79c6",
    accent="#50fa7b",
    success="#50fa7b",
    warning="#f1fa8c",
    error="#ff5555",
    info="#8be9fd",
    muted="#6272a4",
    text="#f8f8f2",
    border="#44475a",
    bg_dark="#282a36",
    bg_light="#3d4055",
    surface="#2d2f3e",
    selection_bg="#44475a",
    inquirer_overrides={
        "questionmark": "bold #ff79c6",
        "pointer": "bold #bd93f9",
    },
)

MONOCHROMATIC_PALETTE = ThemePalette(
    variant=ThemeVariant.MONOCHROMATIC,
    name="Monochromatic",
    primary="#4a9eff",
    secondary="#6b8cbe",
    accent="#ffffff",
    success="#6fcf97",
    warning="#f2c94c",
    error="#eb5757",
    info="#bbbbbb",
    muted="#888888",
    text="#e0e0e0",
    border="#555555",
    bg_dark="#1a1a1a",
    bg_light="#2a2a2a",
    surface="#222222",
    selection_bg="#333333",
    inquirer_overrides={},
)

# Map from enum to palette instance
PALETTE_MAP: dict[ThemeVariant, ThemePalette] = {
    ThemeVariant.CYBERPUNK: CYBERPUNK_PALETTE,
    ThemeVariant.DRACULA: DRACULA_PALETTE,
    ThemeVariant.MONOCHROMATIC: MONOCHROMATIC_PALETTE,
}


# =============================================================================
# ThemeEngine — singleton with depth adaptation
# =============================================================================


class ThemeEngine:
    """Singleton that holds the current :class:`ThemePalette` and adapts it
    to the terminal's colour depth.

    Usage::

        engine = ThemeEngine.get_instance()
        engine.set_theme(ThemeVariant.DRACULA)
        style = engine.style("primary", bold=True)
        inq_style = engine.get_inquirer_style()
    """

    _instance: ThemeEngine | None = None

    def __init__(self) -> None:
        self._palette: ThemePalette = CYBERPUNK_PALETTE
        self._color_depth: str = "truecolor"  # default, overridden on first use
        self._depth_adapted: bool = False

    # ── Singleton access ─────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> ThemeEngine:
        """Return the singleton :class:`ThemeEngine` instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for testing)."""
        cls._instance = None

    # ── Theme management ─────────────────────────────────────────────

    @property
    def palette(self) -> ThemePalette:
        """Return the current palette."""
        return self._palette

    def set_theme(self, variant: ThemeVariant | str) -> ThemePalette:
        """Switch to a new theme by enum or string name.

        Args:
            variant: A :class:`ThemeVariant` member or a string like ``"dracula"``.

        Returns:
            The newly activated :class:`ThemePalette`.
        """
        if isinstance(variant, str):
            variant = ThemeVariant.from_string(variant)
        self._palette = PALETTE_MAP.get(variant, CYBERPUNK_PALETTE)
        self._depth_adapted = False
        return self._palette

    def adapt_to_depth(self, color_depth: str = "") -> ThemePalette:
        """Reduce palette colours to fit the terminal's colour depth.

        Args:
            color_depth: One of ``"truecolor"``, ``"256"``, ``"16"``, ``"mono"``.
                         If empty, auto-detect via env vars.

        Returns:
            The (possibly adapted) palette.
        """
        if self._depth_adapted and (
            not color_depth or color_depth == self._color_depth
        ):
            return self._palette

        if not color_depth:
            ct = os.environ.get("COLORTERM", "").lower()
            if "truecolor" in ct or "24bit" in ct:
                color_depth = "truecolor"
            else:
                term = os.environ.get("TERM", "")
                if "256" in term or term in ("xterm-256color", "screen-256color"):
                    color_depth = "256"
                else:
                    color_depth = "16"

        self._color_depth = color_depth
        self._depth_adapted = True

        if color_depth == "truecolor":
            return self._palette  # No adaptation needed

        # For 256 / 16 colour terminals we keep the palette as-is since
        # Rich and InquirerPy handle colour approximation automatically.
        # We just flag that we *know* we are in reduced colour mode.
        return self._palette

    # ── Style creation ───────────────────────────────────────────────

    def style(
        self,
        token: str,
        *,
        bold: bool = False,
        italic: bool = False,
        dim: bool = False,
        underline: bool = False,
    ) -> Style:
        """Create a Rich :class:`Style` from a palette token name.

        Args:
            token: One of ``"primary"``, ``"secondary"``, ``"accent"``,
                   ``"success"``, ``"warning"``, ``"error"``, ``"info"``,
                   ``"muted"``, ``"text"``, ``"border"``, ``"bg_dark"``.
            bold: Apply bold weight.
            italic: Apply italic slant.
            dim: Dim the colour.
            underline: Underline the text.

        Returns:
            A configured :class:`Style` instance.
        """
        colour = getattr(self._palette, token, self._palette.text)
        return Style(
            color=colour, bold=bold, italic=italic, dim=dim, underline=underline
        )

    def styled_text(self, token: str, text: str, **style_kwargs: Any) -> Text:
        """Return a :class:`Text` object styled with the given token."""
        return Text(text, style=self.style(token, **style_kwargs))

    # ── InquirerPy dynamic style ─────────────────────────────────────

    def get_inquirer_style(self) -> Any:
        """Return a style dict suitable for ``InquirerPy.get_style()``.

        This method builds styles dynamically from the current palette so
        that switching themes instantly updates all InquirerPy prompts.
        """
        p = self._palette
        base = {
            "questionmark": f"bold {p.accent}",
            "answer": f"bold {p.primary}",
            "input": p.muted,
            "question": f"bold {p.primary}",
            "answered_question": f"bold {p.secondary}",
            "instruction": f"italic {p.muted}",
            "pointer": f"bold {p.primary}",
            "checkbox": p.secondary,
            "separator": f"dim {p.muted}",
            "validator": f"bold {p.error}",
            "selection": f"bold {p.accent}",
            "selected": f"bold {p.primary}",
            "selected_label": p.success,
            "unselected_label": p.muted,
            "answered_pointer": p.secondary,
        }
        # Merge per-variant overrides
        base.update(p.inquirer_overrides)

        # الحل: تحويل القاموس لكائن ستايل حقيقي تفهمه المكتبة
        from InquirerPy.utils import get_style

        return get_style(base)


# =============================================================================
# FileTreePreview — renders a scaffold blueprint as a Rich Tree
# =============================================================================


class FileTreePreview:
    """Build a Rich :class:`Tree` showing the files that will be generated.

    Usage::

        preview = FileTreePreview()
        tree = preview.build(files=[
            ("project_name/settings.py", 512),
            ("project_name/urls.py", 128),
            ("apps/users/models.py", 2048),
        ])
        console.print(tree)
    """

    def __init__(self, engine: ThemeEngine | None = None) -> None:
        self._engine = engine or ThemeEngine.get_instance()

    def build(
        self,
        files: list[tuple[str, int]],
        *,
        title: str = "Scaffold Preview",
        show_sizes: bool = True,
    ) -> Tree:
        """Build a :class:`Tree` from a list of ``(file_path, byte_size)`` tuples.

        Args:
            files: List of ``(relative_path, size_in_bytes)`` entries.
            title: Root node label.
            show_sizes: Whether to append size annotations.

        Returns:
            A :class:`rich.tree.Tree` ready for printing.
        """
        p = self._engine.palette
        tree = Tree(
            Text(title, style=Style(bold=True, color=p.primary)),
            guide_style=p.muted,
        )

        # Group files by top-level directory
        dirs: dict[str, list[tuple[str, int]]] = {}
        standalone_files: list[tuple[str, int]] = []

        for path, size in files:
            parts = Path(path).parts
            if len(parts) > 1:
                top = parts[0]
                dirs.setdefault(top, []).append((str(Path(*parts[1:])), size))
            else:
                standalone_files.append((path, size))

        folder_glyph = icon("folder")
        file_glyph = icon("file")

        # Render top-level directories
        for dir_name, children in sorted(dirs.items()):
            dir_node = tree.add(
                Text(
                    f"{folder_glyph}  {dir_name}/",
                    style=Style(bold=True, color=p.secondary),
                )
            )
            for sub_path, size in sorted(children, key=lambda x: x[0]):
                label = f"{file_glyph}  {sub_path}"
                if show_sizes:
                    label += f"  ({self._format_size(size)})"
                dir_node.add(Text(label, style=Style(color=p.text)))

        # Render standalone files
        for path, size in sorted(standalone_files, key=lambda x: x[0]):
            label = f"{file_glyph}  {path}"
            if show_sizes:
                label += f"  ({self._format_size(size)})"
            tree.add(Text(label, style=Style(color=p.text)))

        return tree

    @staticmethod
    def _format_size(bytes_: int) -> str:
        """Human-readable file size (e.g. ``"1.2 KB"``)."""
        if bytes_ < 1024:
            return f"{bytes_} B"
        elif bytes_ < 1024 * 1024:
            return f"{bytes_ / 1024:.1f} KB"
        return f"{bytes_ / (1024 * 1024):.1f} MB"


# =============================================================================
# LEGACY API — re-exported for backward compatibility
# =============================================================================
# Everything below this line matches the old single-theme module's exports
# so that existing code that does ``from ajo.ui.theme import X`` still works.

_engine = ThemeEngine.get_instance()
_engine.set_theme(ThemeVariant.CYBERPUNK)

#: Legacy InquirerPy style dict (uses the Cyberpunk palette).
INQUIRER_STYLE = _engine.get_inquirer_style()


def state_style(active: bool) -> Style:
    """Return a Rich ``Style`` for a boolean state indicator."""
    token = "success" if active else "error"
    return _engine.style(token, bold=True)


def state_label(
    active: bool, *, active_text: str = "Active", inactive_text: str = "Inactive"
) -> Text:
    """Return a styled ``Text`` for a boolean state."""
    text = active_text if active else inactive_text
    return _engine.styled_text("success" if active else "error", text, bold=True)


def migration_label(needs_migrations: bool, unapplied_count: int) -> Text:
    """Build a styled migration-status label."""
    if needs_migrations:
        return Text(
            "Changes detected",
            style=Style(bold=True, color=Theme.WARNING),
        )
    if unapplied_count > 0:
        return Text(
            f"{unapplied_count} pending migration{'s' if unapplied_count != 1 else ''}",
            style=Style(bold=True, color=Theme.WARNING),
        )
    return Text("Up to date", style=Style(bold=True, color=Theme.SUCCESS))


def ruff_label(exit_code: int | None, line_count: int) -> Text:
    """Build a styled Ruff lint status label."""
    if exit_code is None:
        return Text("Not available", style=Style(italic=True, color=Theme.MUTED))
    if exit_code == 0:
        return Text("Clean", style=Style(bold=True, color=Theme.SUCCESS))
    return Text(
        f"{line_count} issue{'s' if line_count != 1 else ''} found",
        style=Style(bold=True, color=Theme.WARNING),
    )


def server_label(running: bool) -> Text:
    """Build a styled server-status label."""
    return state_label(running, active_text="Running", inactive_text="Stopped")


def venv_label(active: bool) -> Text:
    """Build a styled virtualenv-status label."""
    return state_label(active, active_text="Active", inactive_text="Inactive")


def command_urgency_style(is_urgent: bool) -> str:
    """Return a Rich markup tag for a command choice urgency level."""
    if is_urgent:
        return f"bold {Theme.WARNING}"
    return ""
