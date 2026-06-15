"""Rich and InquirerPy style configuration for the ajo-cli TUI.

This module builds on the pure-data constants in :mod:`ajo.core.constants`
and produces concrete style objects ready for use by UI functions.
"""

from __future__ import annotations

from typing import Optional

from InquirerPy.utils import get_style as get_inquirer_style
from rich.style import Style
from rich.text import Text

from ajo.core.constants import Theme

# =============================================================================
# INQUIRER STYLE
# =============================================================================

INQUIRER_STYLE = get_inquirer_style(
    {
        "questionmark": f"bold {Theme.ACCENT}",
        "answer": f"bold {Theme.PRIMARY}",
        "input": Theme.MUTED,
        "question": f"bold {Theme.PRIMARY}",
        "answered_question": f"bold {Theme.SECONDARY}",
        "instruction": f"italic {Theme.MUTED}",
        "pointer": f"bold {Theme.PRIMARY}",
        "checkbox": Theme.SECONDARY,
        "separator": f"dim {Theme.MUTED}",
        "validator": f"bold {Theme.ERROR}",
        "selection": f"bold {Theme.ACCENT}",
    }
)


# =============================================================================
# DYNAMIC STATE HELPERS
# =============================================================================


def state_style(active: bool) -> Style:
    """Return a Rich ``Style`` for a boolean state indicator.

    Args:
        active: ``True`` for good/on state, ``False`` for error/off.

    Returns:
        A bold style using :attr:`Theme.SUCCESS` when *active* is
        ``True``, or :attr:`Theme.ERROR` otherwise.
    """
    return Style(bold=True, color=Theme.SUCCESS if active else Theme.ERROR)


def state_label(
    active: bool, *, active_text: str = "Active", inactive_text: str = "Inactive"
) -> Text:
    """Return a styled ``Text`` for a boolean state.

    Args:
        active: The active/inactive state.
        active_text: Label used when *active* is ``True``.
        inactive_text: Label used when *active* is ``False``.

    Returns:
        A ``Text`` instance with the appropriate style applied.
    """
    text = active_text if active else inactive_text
    style = state_style(active)
    return Text(text, style=style)


def migration_label(needs_migrations: bool, unapplied_count: int) -> Text:
    """Build a styled migration-status label.

    Args:
        needs_migrations: Whether model changes are detected.
        unapplied_count: Count of unapplied migrations.

    Returns:
        A ``Text`` instance with colour-coded urgency styling.
    """
    if needs_migrations:
        return Text(
            f"⚠️  Changes detected (model changes)",
            style=Style(bold=True, color=Theme.WARNING),
        )
    if unapplied_count > 0:
        return Text(
            f"⚠️  {unapplied_count} pending migration{'s' if unapplied_count != 1 else ''}",
            style=Style(bold=True, color=Theme.WARNING),
        )
    return Text("Up to date  ✅", style=Style(bold=True, color=Theme.SUCCESS))


def ruff_label(exit_code: Optional[int], line_count: int) -> Text:
    """Build a styled Ruff lint status label.

    Args:
        exit_code: ``0`` for clean, ``1`` for issues, ``None`` if ruff
            was not found.
        line_count: Number of lint violations reported.

    Returns:
        A ``Text`` instance with appropriate colouring.
    """
    if exit_code is None:
        return Text("Not available", style=Style(italic=True, color=Theme.MUTED))
    if exit_code == 0:
        return Text("Clean  ✅", style=Style(bold=True, color=Theme.SUCCESS))
    return Text(
        f"⚠️  {line_count} issue{'s' if line_count != 1 else ''} found",
        style=Style(bold=True, color=Theme.WARNING),
    )


def server_label(running: bool) -> Text:
    """Build a styled server-status label."""
    return state_label(running, active_text="Running  🟢", inactive_text="Stopped  🔴")


def venv_label(active: bool) -> Text:
    """Build a styled virtualenv-status label."""
    return state_label(active, active_text="Active  🔒", inactive_text="Inactive  🔓")


def command_urgency_style(is_urgent: bool) -> str:
    """Return a Rich markup tag for a command choice urgency level.

    Args:
        is_urgent: Whether the command should be visually promoted.

    Returns:
        A Rich markup string — e.g. ``"bold #ffb86c"`` for urgent,
        ``""`` (no styling) for normal.
    """
    if is_urgent:
        return f"bold {Theme.WARNING}"
    return ""
