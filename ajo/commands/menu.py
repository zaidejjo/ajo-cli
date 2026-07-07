"""Main interactive menu for ajo-cli.

Provides :func:`show_main_menu` which renders a welcome banner and
action-selection prompt using Rich and InquirerPy.

Usage from ``ajo.cli``::

    from ajo.commands.menu import show_main_menu

    action = await show_main_menu(inquirer_style=INQUIRER_STYLE)
    if action is None:
        return 130  # user pressed Ctrl+C
    # route action...
"""

from __future__ import annotations

from dataclasses import dataclass

from ajo import __version__
from ajo.ui.icons import (
    ICON_EXIT,
    ICON_FILE,
    ICON_HEART_PULSE,
    ICON_HISTORY,
    ICON_ROCKET,
    ICON_SEARCH,
    ICON_TERMINAL,
    ICON_UPGRADE,
)
from ajo.ui.theme import Theme


@dataclass(frozen=True)
class MenuItem:
    """A single entry in the main menu.

    Attributes:
        action: Machine-readable action string returned to the caller.
        label: Human-readable display label.
        icon: Nerd Font or fallback icon string.
        hint: Optional short hint shown dimmed next to the label.
    """

    action: str
    label: str
    icon: str = ""
    hint: str = ""


# ── Menu definition ─────────────────────────────────────────────────────
# Order here determines display order.
_MENU_ITEMS: list[MenuItem] = [
    MenuItem("new_project", "Create New Project", ICON_ROCKET),
    MenuItem("scan", "Scan Django Project", ICON_SEARCH, "[scan]"),
    MenuItem("doctor", "Run Diagnostics", ICON_HEART_PULSE, "[doctor]"),
    MenuItem("report", "Generate Report", ICON_FILE, "[report]"),
    MenuItem("upgrade", "Check for Updates", ICON_UPGRADE, "[upgrade]"),
    MenuItem("changelog", "View Changelog", ICON_HISTORY, "[changelog]"),
    MenuItem("completion", "Shell Completions", ICON_TERMINAL, "[completion]"),
]


def _build_choices() -> list:
    """Build the list of InquirerPy Choice objects for the menu.

    Returns:
        A list of ``Choice`` and ``Separator`` objects ready for
        ``inquirer.select()``.
    """
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator

    choices: list[Choice | Separator] = []
    for item in _MENU_ITEMS:
        name = f"  {item.icon}  {item.label}"
        if item.hint:
            name += f"  [dim {Theme.MUTED}]{item.hint}[/]"
        choices.append(Choice(value=item.action, name=name))

    choices.append(Separator())
    choices.append(Choice(value="exit", name=f"  {ICON_EXIT}  Exit"))
    return choices


async def show_main_menu(
    *,
    inquirer_style: object = None,
) -> str | None:
    """Render the welcome banner and interactive action menu.

    The banner displays version information using a Rich ``Panel``.
    The menu is an InquirerPy ``select`` prompt with vi-mode navigation
    and cycle enabled.

    Args:
        inquirer_style: Optional ``InquirerPy.style.CustomStyle`` to
            apply to the prompt.  Pass the module-level
            ``INQUIRER_STYLE`` from ``ajo.cli`` or ``ajo.ui.theme``
            for consistent theming.

    Returns:
        An action string from :data:`_MENU_ITEMS` (e.g. ``"new_project"``,
        ``"doctor"``) or ``None`` if the user cancelled via ``Ctrl+C``
        / ``Esc``.
    """
    from rich.panel import Panel
    from rich.text import Text

    from InquirerPy import inquirer

    from ajo.cli import console  # noqa: PLC0415 — lazy import
    from ajo.core.constants import qmark

    # ── Welcome banner ────────────────────────────────────────────────
    title = Text()
    title.append(f"{ICON_ROCKET}  ", style=f"bold {Theme.PRIMARY}")
    title.append("ajo", style=f"bold {Theme.PRIMARY}")
    title.append(f"  v{__version__}", style=f"dim {Theme.MUTED}")

    subtitle = Text(
        "Professional Django scaffolder",
        style=f"italic dim {Theme.MUTED}",
    )

    banner = Panel(
        subtitle,
        title=title,
        title_align="left",
        border_style=Theme.PRIMARY,
        padding=(1, 2),
    )

    console.print()
    console.print(banner)
    console.print()

    # ── Menu prompt ───────────────────────────────────────────────────
    choices = _build_choices()

    try:
        action: str = inquirer.select(
            message="What would you like to do?",
            choices=choices,
            style=inquirer_style,
            qmark=qmark(),
            vi_mode=True,
            cycle=True,
        ).execute()
    except KeyboardInterrupt:
        console.print()
        return None

    return action
