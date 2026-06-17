"""Fuzzy finding and filtered selection utilities.

Provides the :class:`FuzzyFinder` class that wraps InquirerPy with
fuzzy-matching capabilities for app selection and command filtering.
"""

from __future__ import annotations

from typing import Any

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from InquirerPy.validator import ValidationError, Validator
from InquirerPy.utils import get_style

from ajo.ui.theme import ThemeEngine


# ── Minimal fuzzy filter ─────────────────────────────────────────────────


def _fuzzy_filter(items: list[str], query: str) -> list[str]:
    """Simple substring + character-order fuzzy matcher.

    Returns *items* that match *query* in order, with the best matches
    first.  This is intentionally lightweight (no external dependency).
    """
    if not query:
        return list(items)

    query_lower = query.lower()

    def score(item: str) -> float:
        il = item.lower()
        # Exact match gets highest score
        if query_lower == il:
            return 1000.0
        # Starts with the query
        if il.startswith(query_lower):
            return 500.0 + len(item)
        # Substring match
        if query_lower in il:
            return 100.0 + len(item)
        # Character-order fuzzy match
        it = iter(il)
        if all(c in it for c in query_lower):
            return 10.0 + len(item)
        return 0.0

    scored = [(s, item) for item in items if (s := score(item)) > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [item for _, item in scored]


# ── Validator for app name input ─────────────────────────────────────────


class AppNameValidator(Validator):
    """Validate that the app name matches Django's conventions."""

    def validate(self, document: Any) -> None:
        text = document.text.strip()
        if not text:
            raise ValidationError(message="App name cannot be empty")
        if not text.isidentifier():
            raise ValidationError(message=f"'{text}' is not a valid Python identifier")


# ── FuzzyFinder ──────────────────────────────────────────────────────────


class FuzzyFinder:
    """Interactive fuzzy-finding helpers for the ajo-cli TUI.

    All methods are async / sync wrappers around InquirerPy prompts that
    apply fuzzy filtering to reduce typing effort.
    """

    def __init__(self, engine: ThemeEngine | None = None) -> None:
        self._engine = engine or ThemeEngine.get_instance()
        self._inquirer_style = self._engine.get_inquirer_style()

    # ── App selection (multi-select checkbox with fuzzy filter) ───────

    async def select_apps(
        self,
        available_apps: list[str],
        *,
        message: str = "Select Django apps to scaffold:",
        default_apps: list[str] | None = None,
        min_apps: int = 1,
    ) -> list[str]:
        """Show a fuzzy-filtered multi-select of Django app names.

        The user can type to filter the app list in real time.

        Args:
            available_apps: All app names to show.
            message: Prompt message.
            default_apps: Pre-selected app names.
            min_apps: Minimum number of apps required.

        Returns:
            List of selected app names.
        """
        default_apps = default_apps or []
        choices: list[Choice | Separator] = [
            Separator(line="─" * 30),
        ]

        for app in available_apps:
            enabled = app in default_apps
            choices.append(Choice(value=app, name=app, enabled=enabled))

        # Apply fuzzy filter if there are many apps
        if len(available_apps) > 10:
            filter_query = await self._fuzzy_input("Filter apps (type to search):")
            if filter_query:
                matched = _fuzzy_filter(available_apps, filter_query)
                choices = [
                    Choice(value=app, name=app, enabled=app in default_apps)
                    for app in matched
                ]

        selected = await inquirer.checkbox(
            message=message,
            choices=choices,
            cycle=True,
            style=self._inquirer_style,
            validate=lambda result: (
                len(result) >= min_apps or f"Select at least {min_apps} app(s)"
            ),
            transformer=lambda result: (
                f"{len(result)} app(s) selected" if result else "None selected"
            ),
        ).execute_async()

        return selected

    # ── Command filtering ─────────────────────────────────────────────

    async def filter_commands(
        self,
        commands: dict[str, str],
        *,
        message: str = "Search commands:",
    ) -> str | None:
        """Fuzzy-search through available commands.

        Args:
            commands: ``{display_label: action_name}`` map.
            message: Prompt message.

        Returns:
            The selected action name, or ``None`` if cancelled.
        """
        if not commands:
            return None

        names = list(commands.keys())
        filter_query = await self._fuzzy_input(message)

        if filter_query:
            matched = _fuzzy_filter(names, filter_query)
        else:
            matched = names

        if not matched:
            return None

        # Show filtered list for final selection
        choice_objects = [Choice(value=commands[n], name=n) for n in matched]
        result = await inquirer.select(
            message="Select command:",
            choices=choice_objects,
            style=self._inquirer_style,
            cycle=True,
        ).execute_async()

        return result

    # ── Generic fuzzy text input ──────────────────────────────────────

    async def fuzzy_input(
        self,
        message: str = "Search:",
        *,
        default: str = "",
        validate: Validator | None = None,
    ) -> str:
        """Prompt for a fuzzy search string.

        Args:
            message: Prompt message.
            default: Default input value.
            validate: Optional custom validator.

        Returns:
            The entered string.
        """
        result = await inquirer.text(
            message=message,
            default=default,
            style=self._inquirer_style,
            validate=validate,
            qmark="🔍",
        ).execute_async()
        return result.strip()

    # ── Internal: async fuzzy input helper ────────────────────────────

    async def _fuzzy_input(self, message: str) -> str:
        """Short internal helper for a quick filter text input."""
        try:
            result = await inquirer.text(
                message=message,
                style=self._inquirer_style,
                qmark="🔍",
            ).execute_async()
            return result.strip()
        except Exception:
            return ""

    # ── Synchronous convenience methods ───────────────────────────────

    def select_apps_sync(
        self,
        apps: list[str],
        **kwargs: Any,
    ) -> list[str]:
        """Synchronous version of :meth:`select_apps`."""
        import asyncio

        return asyncio.run(self.select_apps(apps, **kwargs))

    def filter_commands_sync(
        self,
        commands: dict[str, str],
        **kwargs: Any,
    ) -> str | None:
        """Synchronous version of :meth:`filter_commands`."""
        import asyncio

        return asyncio.run(self.filter_commands(commands, **kwargs))
