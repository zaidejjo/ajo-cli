"""Smart context-aware CLI commands for Django project management.

The :class:`SmartDjangoCLI` analyses the current project state and
dynamically reorders / prioritises management commands so the most
pressing actions appear first (e.g. pending migrations, missing
superuser).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ajo.detector.project import DjangoProjectDetector

from ajo.core.constants import NF


class SmartCommand:
    """A single command item produced by :class:`SmartDjangoCLI`.

    Attributes:
        name: Human-readable label (e.g. ``"Apply Migrations (2 pending)"``).
        action: Machine-actionable key (e.g. ``"migrate"``).
        description: One-line explanation for tooltip / help text.
        icon: Nerd Font icon codepoint.
        urgency: ``True`` if this command should be visually promoted
            (highlighted, reordered to top).
    """

    def __init__(
        self,
        name: str,
        action: str,
        description: str = "",
        icon: str = "",
        urgency: bool = False,
    ) -> None:
        self.name = name
        self.action = action
        self.description = description
        self.icon = icon
        self.urgency = urgency


class SmartDjangoCLI:
    """Context-aware command provider that reorders commands by project state.

    Usage::

        detector = DjangoProjectDetector(path)
        smart = SmartDjangoCLI(detector)
        for cmd in smart.get_commands():
            print(cmd.name)
    """

    def __init__(self, detector: DjangoProjectDetector) -> None:
        self.detector = detector

    def get_commands(self) -> list[SmartCommand]:
        """Return commands ordered by contextual priority.

        Commands related to pending migrations are promoted to the top
        with urgency badges.  Normal commands follow in a sensible
        default order.
        """
        info = self.detector.project_info
        base: list[SmartCommand] = [
            SmartCommand(
                name="Run Server",
                action="runserver",
                description="Start development server",
                icon=NF.SERVER,
            ),
            SmartCommand(
                name="Create Superuser",
                action="createsuperuser",
                description="Create admin user",
                icon=NF.USER,
            ),
            SmartCommand(
                name="Run Tests",
                action="test",
                description="Run all tests",
                icon=NF.TEST,
            ),
            SmartCommand(
                name="Create App",
                action="create_app",
                description="Scaffold a new app",
                icon=NF.APP,
            ),
            SmartCommand(
                name="Django Shell",
                action="shell",
                description="Open Django shell",
                icon=NF.TERMINAL,
            ),
        ]

        dynamic: list[SmartCommand] = []

        # ── Pending migrations detection ─────────────────────────────
        if info.get("needs_migrations"):
            base = [c for c in base if c.action != "makemigrations"]
            dynamic.append(
                SmartCommand(
                    name="Make Migrations (needed)",
                    action="makemigrations",
                    description="Model changes detected — run this first",
                    icon=NF.MIGRATION,
                    urgency=True,
                )
            )

        unapplied = len(info.get("unapplied_migrations", []))
        if unapplied > 0:
            base = [c for c in base if c.action != "migrate"]
            dynamic.append(
                SmartCommand(
                    name=f"Apply Migrations ({unapplied} pending)",
                    action="migrate",
                    description=f"Apply {unapplied} pending migration(s)",
                    icon=NF.MIGRATION,
                    urgency=True,
                )
            )

        # ── Missing superuser detection ──────────────────────────────
        has_superuser = info.get("has_superuser", False)
        if not has_superuser:
            base = [c for c in base if c.action != "createsuperuser"]
            dynamic.append(
                SmartCommand(
                    name="Create Superuser (needed)",
                    action="createsuperuser",
                    description="No admin user found — create one now",
                    icon=NF.USER,
                    urgency=True,
                )
            )

        # ── Ruff lint issues ─────────────────────────────────────────
        ruff_result = info.get("ruff_result")
        if (
            ruff_result is not None
            and ruff_result.exit_code is not None
            and ruff_result.exit_code != 0
        ):
            base = [c for c in base if c.action != "lint_check"]
            dynamic.append(
                SmartCommand(
                    name=f"Fix Ruff Issues ({ruff_result.line_count})",
                    action="lint_check",
                    description=f"Ruff found {ruff_result.line_count} lint violation(s)",
                    icon=NF.RUFF,
                    urgency=True,
                )
            )

        # ── Normal migration commands (no urgency) ───────────────────
        if not any(c.action == "makemigrations" for c in dynamic):
            base.insert(
                1,
                SmartCommand(
                    name="Make Migrations",
                    action="makemigrations",
                    description="Create new migrations",
                    icon=NF.MIGRATION,
                ),
            )
        if not any(c.action == "migrate" for c in dynamic):
            base.insert(
                2,
                SmartCommand(
                    name="Apply Migrations",
                    action="migrate",
                    description="Apply migrations",
                    icon=NF.MIGRATION,
                ),
            )

        # ── Clear cache (always at the end) ──────────────────────────
        base.append(
            SmartCommand(
                name="Clear Cache",
                action="clear_cache",
                description="Remove __pycache__ directories",
                icon=NF.CACHE,
            ),
        )

        return dynamic + base
