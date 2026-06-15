#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         AJO CLI - Professional Django Scaffolder              ║
║                         Cyberpunk Edition · Enterprise Ready                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import argparse
import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

try:
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from InquirerPy.validator import ValidationError, Validator
except ImportError:
    print("❌ InquirerPy not installed. Run: uv pip install InquirerPy")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TimeElapsedColumn,
    )
    from rich import box
    from rich.align import Align
    from rich.rule import Rule
except ImportError:
    print("❌ Rich not installed. Run: uv pip install rich")
    sys.exit(1)

# Local imports
from ajo import __version__
from ajo.core.app import async_entry
from ajo.core.constants import NF, Theme
from ajo.core.exceptions import AjoError, PresetError
from ajo.detector import DjangoProjectDetector, SmartDjangoCLI, SmartCommand
from ajo.detector.prereqs import check_uv_installed
from ajo.presets import get_preset, list_presets
from ajo.scaffolding import ScaffoldEngine
from ajo.templates.django_app import DjangoProjectScaffolder
from ajo.ui.theme import (
    INQUIRER_STYLE,
    command_urgency_style,
    migration_label,
    ruff_label,
    server_label,
    state_label,
    venv_label,
)
from ajo.validators import ProjectNameValidator

# Global console
console = Console()


# =============================================================================
# CUSTOM VALIDATORS
# =============================================================================


class AppNameValidator(Validator):
    """Django app name validation."""

    PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    RESERVED = {"django", "test", "tests", "site", "admin", "config", "settings"}

    def validate(self, document):
        value = document.text.strip()

        if not value:
            raise ValidationError("App name cannot be empty")

        if len(value) < 2:
            raise ValidationError("App name must be at least 2 characters")

        if not self.PATTERN.match(value):
            raise ValidationError(
                "Use only letters and underscores. Must start with a letter."
            )

        if value.lower() in self.RESERVED:
            raise ValidationError(f"'{value}' is a reserved Django app name")

        return True


# =============================================================================
# UI FUNCTIONS
# =============================================================================


def center(content, width: Optional[int] = None):
    """Center content on screen."""
    return Align.center(content, width=width)


def print_rule(title: str = "", style: str = Theme.MUTED):
    """Print a horizontal rule."""
    console.print(Rule(title=title, style=f"dim {style}"))


def print_banner():
    """Display animated cyberpunk banner."""
    banner = """
                ╔════════════════════════════════════════════════════╗
                ║                                                    ║
                ║              █████╗      ██╗ ██████╗               ║
                ║             ██╔══██╗     ██║██╔═══██╗              ║
                ║             ███████║     ██║██║   ██║              ║
                ║             ██╔══██║██   ██║██║   ██║              ║
                ║             ██║  ██║╚█████╔╝╚██████╔╝              ║
                ║             ╚═╝  ╚═╝ ╚════╝  ╚═════╝               ║
                ║                                                    ║
                ╚════════════════════════════════════════════════════╝
"""

    for line in banner.split("\n"):
        if "█" in line or "╔" in line or "╚" in line:
            console.print(f"[{Theme.SECONDARY}]{line}[/]")
        elif "Professional" in line or "Cyberpunk" in line:
            console.print(f"[bold {Theme.ACCENT}]{line}[/]")
        elif line.strip():
            console.print(f"[{Theme.MUTED}]{line}[/]")

    # Tech badges
    badges = f"""
{center(f"[{Theme.SUCCESS}]{NF.PYTHON} Python 3.10+[/]  [{Theme.PRIMARY}]{NF.DJANGO} Django 5.0+[/]  [{Theme.SECONDARY}]{NF.UV} uv Package Manager[/]  [{Theme.ACCENT}]{NF.RUFF} Ruff Linter[/]")}
"""
    console.print(badges)
    console.print()


def show_error(title: str, message: str, suggestion: Optional[str] = None):
    """Display error panel."""
    content = Text()
    content.append(f"\n  {NF.ERROR}  ", style=f"bold {Theme.ERROR}")
    content.append(message, style=Theme.ERROR)

    if suggestion:
        content.append(f"\n\n  {NF.ARROW_RIGHT}  ", style=f"dim {Theme.MUTED}")
        content.append(suggestion, style=f"italic {Theme.WARNING}")

    panel = Panel(
        content,
        title=f"  {NF.ERROR}  {title}  ",
        title_align="center",
        border_style=Theme.ERROR,
        padding=(1, 2),
    )
    console.print(center(panel))
    console.print()


def show_success(title: str, message: str):
    """Display success panel."""
    content = Text()
    content.append(f"\n  {NF.CHECK}  ", style=f"bold {Theme.SUCCESS}")
    content.append(message, style=Theme.SUCCESS)

    panel = Panel(
        content,
        title=f"  {NF.CHECK}  {title}  ",
        title_align="center",
        border_style=Theme.SUCCESS,
        padding=(1, 2),
    )
    console.print(center(panel))
    console.print()


def show_info(title: str, message: str):
    """Display info panel."""
    content = Text()
    content.append(f"\n  {NF.INFO}  ", style=f"bold {Theme.PRIMARY}")
    content.append(message, style=Theme.MUTED)

    panel = Panel(
        content,
        title=f"  {NF.INFO}  {title}  ",
        title_align="center",
        border_style=Theme.SECONDARY,
        padding=(1, 2),
    )
    console.print(center(panel))
    console.print()


def show_warning(title: str, message: str):
    """Display warning panel."""
    content = Text()
    content.append(f"\n  {NF.WARNING}  ", style=f"bold {Theme.WARNING}")
    content.append(message, style=Theme.WARNING)

    panel = Panel(
        content,
        title=f"  {NF.WARNING}  {title}  ",
        title_align="center",
        border_style=Theme.WARNING,
        padding=(1, 2),
    )
    console.print(center(panel))
    console.print()


# =============================================================================
# FEATURE GRID
# =============================================================================


def show_features():
    """Display feature grid."""
    console.print()
    print_rule("Features")
    console.print()

    # Core features table
    features_table = Table(
        box=box.ROUNDED, border_style=Theme.BORDER, show_header=False
    )
    features_table.add_column("", style=Theme.ACCENT, width=4)
    features_table.add_column("", style=Theme.PRIMARY, width=28)
    features_table.add_column("", style=Theme.ACCENT, width=4)
    features_table.add_column("", style=Theme.PRIMARY, width=28)

    features = [
        (NF.DATABASE, "Multi-Database Support"),
        (NF.GITHUB, "GitHub Integration"),
        (NF.RUFF, "CI/CD with Ruff"),
        (NF.LOCK, "Auto .env Security"),
        (NF.APP, "Multiple Apps Support"),
        (NF.TEST, "Testing Framework"),
        (NF.DOCKER, "Docker Support"),
        (NF.STACK, "Bootstrap 5 Themes"),
        (NF.SHELL, "Django Shell Plus"),
        (NF.DEBUG, "Debug Toolbar Ready"),
    ]

    for i in range(0, len(features), 2):
        icon1, text1 = features[i]
        if i + 1 < len(features):
            icon2, text2 = features[i + 1]
            features_table.add_row(f"  {icon1}  ", text1, f"  {icon2}  ", text2)
        else:
            features_table.add_row(f"  {icon1}  ", text1, "", "")

    panel = Panel(
        features_table,
        title=f"  {NF.STAR}  Core Features  ",
        title_align="center",
        border_style=Theme.SECONDARY,
    )
    console.print(center(panel, width=90))
    console.print()

    # Architecture presets
    arch_table = Table(box=box.ROUNDED, border_style=Theme.BORDER, show_header=True)
    arch_table.add_column("Preset", style=f"bold {Theme.ACCENT}")
    arch_table.add_column("Description", style=Theme.PRIMARY)
    arch_table.add_column("Components", style=Theme.MUTED)

    arch_table.add_row(
        f"{NF.STACK} Standard Monolith",
        "Traditional Django with templates",
        "HTML + Bootstrap 5 + HTMX",
    )
    arch_table.add_row(
        f"{NF.ROCKET} REST API Ready",
        "DRF + CORS pre-configured",
        "DRF + JWT + CORS + Swagger",
    )
    arch_table.add_row(
        f"{NF.CODE} GraphQL API", "Graphene + Django", "Graphene + GraphiQL + Relay"
    )
    arch_table.add_row(
        f"{NF.SERVER} Full-Stack Modern",
        "Django + React/Vue/Alpine",
        "REST API + Frontend integration",
    )

    panel = Panel(
        arch_table,
        title=f"  {NF.GEAR}  Architecture Presets  ",
        title_align="center",
        border_style=Theme.PRIMARY,
    )
    console.print(center(panel, width=90))
    console.print()


# =============================================================================
# PREREQUISITES CHECK
# =============================================================================


def check_prerequisites() -> bool:
    """Check system prerequisites."""
    print_rule("System Prerequisites")
    console.print()

    all_ok = True

    # Python
    py_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    console.print(
        f"  {NF.CHECK}  [{Theme.SUCCESS}]Python 3.10+{' ' * 12}[/] v{py_version}"
    )

    # uv
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        uv_ok = result.returncode == 0
        uv_version = result.stdout.strip().split()[-1] if uv_ok else "Not found"
        if uv_ok:
            console.print(
                f"  {NF.CHECK}  [{Theme.SUCCESS}]UV Package Manager{' ' * 7}[/] {uv_version}"
            )
        else:
            console.print(
                f"  {NF.ERROR}  [{Theme.ERROR}]UV Package Manager{' ' * 7}[/] Not installed"
            )
            all_ok = False
    except FileNotFoundError:
        console.print(
            f"  {NF.ERROR}  [{Theme.ERROR}]UV Package Manager{' ' * 7}[/] Not installed"
        )
        all_ok = False

    # Git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        git_version = (
            result.stdout.strip().split()[-1] if result.returncode == 0 else "Not found"
        )
        console.print(f"  {NF.CHECK}  [{Theme.SUCCESS}]Git{' ' * 24}[/] {git_version}")
    except FileNotFoundError:
        console.print(
            f"  {NF.INFO}  [{Theme.MUTED}]Git{' ' * 24}[/] Not installed (optional)"
        )

    # GitHub CLI
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            gh_version = result.stdout.strip().split()[2]
            console.print(
                f"  {NF.CHECK}  [{Theme.SUCCESS}]GitHub CLI{' ' * 18}[/] {gh_version}"
            )
        else:
            console.print(
                f"  {NF.INFO}  [{Theme.MUTED}]GitHub CLI{' ' * 18}[/] Not installed (optional)"
            )
    except FileNotFoundError:
        console.print(
            f"  {NF.INFO}  [{Theme.MUTED}]GitHub CLI{' ' * 18}[/] Not installed (optional)"
        )

    console.print()

    if not all_ok:
        show_error(
            "Missing Requirements",
            "uv is required for AJO to work properly",
            "Install: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )

    return all_ok


# =============================================================================
# DATABASE SELECTION
# =============================================================================


def select_database() -> Tuple[str, Dict]:
    """Interactive database selection."""
    console.print()
    print_rule("Database Configuration")
    console.print()

    db_table = Table(box=box.ROUNDED, border_style=Theme.BORDER)
    db_table.add_column("", style=Theme.ACCENT, width=4)
    db_table.add_column("Database", style=f"bold {Theme.PRIMARY}")
    db_table.add_column("Description", style=Theme.MUTED)

    db_table.add_row(f"  {NF.SQLITE}  ", "SQLite", "Lightweight, file-based (default)")
    db_table.add_row(
        f"  {NF.POSTGRES}  ", "PostgreSQL", "Production-ready, feature-rich"
    )
    db_table.add_row(f"  {NF.MYSQL}  ", "MySQL", "Popular, reliable")

    console.print(center(Panel(db_table, border_style=Theme.SECONDARY), width=70))
    console.print()

    db_choice = inquirer.select(
        message="Select your database:",
        choices=[
            Choice(value="sqlite", name=f"{NF.SQLITE} SQLite - Development"),
            Choice(value="postgresql", name=f"{NF.POSTGRES} PostgreSQL - Production"),
            Choice(value="mysql", name=f"{NF.MYSQL} MySQL - Production"),
        ],
        style=INQUIRER_STYLE,
        qmark=f"{NF.ARROW_RIGHT}",
        default="sqlite",
    ).execute()

    config = {
        "sqlite": {
            "engine": "django.db.backends.sqlite3",
            "name": "db.sqlite3",
            "user": "",
            "password": "",
            "host": "",
            "port": "",
            "packages": [],
        },
        "postgresql": {
            "engine": "django.db.backends.postgresql",
            "name": "postgres",
            "user": "postgres",
            "password": "",
            "host": "localhost",
            "port": "5432",
            "packages": ["psycopg2-binary"],
        },
        "mysql": {
            "engine": "django.db.backends.mysql",
            "name": "mysql",
            "user": "root",
            "password": "",
            "host": "localhost",
            "port": "3306",
            "packages": ["mysqlclient"],
        },
    }

    selected_config = config[db_choice]

    if db_choice != "sqlite":
        console.print()
        show_info(
            "Database Credentials", "Enter credentials (press Enter for defaults)"
        )

        selected_config["name"] = inquirer.text(
            message="Database name:",
            default=selected_config["name"],
            style=INQUIRER_STYLE,
        ).execute()

        selected_config["user"] = inquirer.text(
            message="Username:",
            default=selected_config["user"],
            style=INQUIRER_STYLE,
        ).execute()

        selected_config["password"] = inquirer.secret(
            message="Password:",
            style=INQUIRER_STYLE,
        ).execute()

        selected_config["host"] = inquirer.text(
            message="Host:",
            default=selected_config["host"],
            style=INQUIRER_STYLE,
        ).execute()

        selected_config["port"] = inquirer.text(
            message="Port:",
            default=selected_config["port"],
            style=INQUIRER_STYLE,
        ).execute()

    return db_choice, selected_config


# =============================================================================
# GITHUB INTEGRATION
# =============================================================================


def setup_github(project_path: Path, project_name: str) -> bool:
    """Setup GitHub repository."""
    console.print()

    use_github = inquirer.confirm(
        message=f"  {NF.GITHUB}  Create a GitHub repository?",
        default=False,
        style=INQUIRER_STYLE,
    ).execute()

    if not use_github:
        return False

    # Check GitHub CLI
    try:
        subprocess.run(["gh", "--version"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        show_error(
            "GitHub CLI Missing",
            "GitHub CLI is not installed",
            "Install: brew install gh",
        )
        return False

    # Check auth
    auth = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if auth.returncode != 0:
        show_error(
            "Not Logged In", "You are not logged into GitHub", "Run: gh auth login"
        )
        return False

    visibility = inquirer.select(
        message="Repository visibility:",
        choices=[
            Choice(value="public", name=f"{NF.GLOBE} Public - Anyone can see"),
            Choice(value="private", name=f"{NF.LOCK} Private - Only you"),
        ],
        style=INQUIRER_STYLE,
    ).execute()

    with Progress(
        SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(f"{NF.GITHUB} Creating repository...", total=None)

        # Init git
        subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from AJO CLI"],
            cwd=project_path,
            capture_output=True,
        )

        # Create and push
        result = subprocess.run(
            [
                "gh",
                "repo",
                "create",
                project_name,
                "--source=.",
                "--remote=origin",
                f"--{visibility}",
                "--push",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            progress.update(
                task, description=f"{NF.CHECK} Repository created!", completed=100
            )
            return True
        else:
            progress.stop()
            show_error("Repository Creation Failed", result.stderr)
            return False


# =============================================================================
# CI/CD SETUP
# =============================================================================


def setup_cicd(project_path: Path) -> bool:
    """Setup GitHub Actions CI/CD."""
    console.print()

    use_cicd = inquirer.confirm(
        message=f"  {NF.RUFF}  Setup CI/CD with GitHub Actions?",
        default=True,
        style=INQUIRER_STYLE,
    ).execute()

    if not use_cicd:
        return False

    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    ci_yml = """name: CI/CD Pipeline

on:
  push:
    branches: [ main, master, develop ]
  pull_request:
    branches: [ main, master ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v3
    - name: Install dependencies
      run: uv sync
    - name: Run Ruff linter
      run: uv run ruff check .
    - name: Run Ruff formatter check
      run: uv run ruff format --check
  
  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v3
    - name: Install dependencies
      run: uv sync
    - name: Run tests
      run: uv run python manage.py test
      env:
        SECRET_KEY: "test-key-not-for-production"
        DEBUG: "False"
  
  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Run security check
      run: |
        uv add bandit
        uv run bandit -r . -x .venv
"""

    (workflows_dir / "ci.yml").write_text(ci_yml)

    show_success("CI/CD Pipeline", "GitHub Actions workflow configured with Ruff")
    return True


# =============================================================================
# REACTIVE DASHBOARD RENDERER
# =============================================================================


class DashboardRenderer:
    """Reactive renderable for :class:`rich.live.Live` progressive dashboard.

    Fast filesystem data (project name, branch, venv) is shown immediately.
    While the slow detection (migrations, ruff) runs in background threads,
    animated spinners are displayed in the relevant cells.  When the slow
    data arrives the spinners are replaced with real styled labels.
    """

    def __init__(self, detector: DjangoProjectDetector) -> None:
        self._detector = detector
        self._slow_loaded = False
        # Persistent spinners (survive render cycles for smooth animation)
        self._spinner_mig = Spinner("dots", style=Theme.PRIMARY)
        self._spinner_ruff = Spinner("arrow2", style=Theme.SECONDARY)

    # ── Public API ───────────────────────────────────────────────────

    def mark_slow_loaded(self) -> None:
        """Signal that slow background detection has completed."""
        self._slow_loaded = True

    # ── Rich renderable ──────────────────────────────────────────────

    def __rich__(self) -> Panel:
        info = self._detector.project_info
        table = Table(box=box.ROUNDED, border_style=Theme.BORDER, show_header=False)
        table.add_column("", style=Theme.ACCENT, width=20)
        table.add_column("", style=Theme.PRIMARY)

        # ── Project Meta ─────────────────────────────────────────────
        table.add_row(f"{NF.FOLDER}  Project", str(info.get("project_name", "Unknown")))
        table.add_row(f"{NF.GIT}  Branch", str(info.get("git_branch", "N/A")))
        table.add_row(
            f"{NF.TERMINAL}  Venv", venv_label(info.get("venv_active", False))
        )

        table.add_row("", "")  # visual spacer

        # ── Live Status ──────────────────────────────────────────────
        table.add_row(
            f"{NF.SERVER}  Server", server_label(info.get("server_running", False))
        )
        table.add_row(f"{NF.APP}  Apps", str(len(info.get("apps", []))))
        table.add_row(f"{NF.MODEL}  Models", str(info.get("models_count", 0)))

        # ── Migrations (spinner until slow scan) ─────────────────────
        if self._slow_loaded:
            needs_mig = info.get("needs_migrations", False)
            unapplied = len(info.get("unapplied_migrations", []))
            table.add_row(
                f"{NF.MIGRATION}  Migrations", migration_label(needs_mig, unapplied)
            )
        else:
            table.add_row(f"{NF.MIGRATION}  Migrations", self._spinner_mig)

        # ── Ruff lint status (spinner until slow scan) ───────────────
        ruff = info.get("ruff_result")
        if self._slow_loaded:
            exit_code = ruff.exit_code if ruff else None
            line_count = ruff.line_count if ruff else 0
            table.add_row(f"{NF.RUFF}  Ruff Lint", ruff_label(exit_code, line_count))
        else:
            table.add_row(f"{NF.RUFF}  Ruff Lint", self._spinner_ruff)

        return Panel(
            table,
            title=f"  {NF.SETTINGS}  Django Project Dashboard  ",
            title_align="center",
            border_style=Theme.PRIMARY,
        )


async def show_dashboard(detector: DjangoProjectDetector) -> bool:
    """Render the live reactive dashboard using :class:`rich.live.Live`.

    While the slow background detection runs (migrations, ruff, superuser
    check), the dashboard displays animated spinners.  Once the data
    arrives, the cells update in-place.

    Args:
        detector: A :class:`DjangoProjectDetector` already initialised.

    Returns:
        ``False`` if the user interrupted (Ctrl+C), ``True`` otherwise.
    """
    renderer = DashboardRenderer(detector)

    try:
        with Live(renderer, refresh_per_second=10, vertical_overflow="visible"):
            # Kick off slow background detection (migrations, ruff, superuser)
            slow_task = asyncio.create_task(detector.detect_slow_async(use_cache=True))

            done, _ = await asyncio.wait([slow_task], timeout=15.0)

            if slow_task in done:
                # Pull latest state from the detector and mark loaded
                try:
                    _ = slow_task.result()  # re-raise if exception
                except Exception:
                    pass
                renderer.mark_slow_loaded()

            # Brief pause so the user can admire the final state
            await asyncio.sleep(0.8)
    except KeyboardInterrupt:
        console.print()
        return False

    return True


# =============================================================================
# SMART COMMANDS
# =============================================================================


async def run_command_async(
    action: str, project_path: Path, *, scaffolder=None
) -> bool:
    """Execute a management command asynchronously.

    Interactive commands (``runserver``, ``shell``, ``createsuperuser``)
    inherit the terminal so the user can interact with them directly.
    Non-interactive commands (``makemigrations``, ``migrate``, ``test``)
    capture output and show it on success, or display a rich error panel
    on failure.

    Args:
        action: The command action key.
        project_path: Root of the Django project.
        scaffolder: Optional :class:`DjangoProjectScaffolder` for
            ``create_app``.

    Returns:
        ``True`` if the command succeeded or was cancelled gracefully,
        ``False`` on errors.
    """

    # ── Internal actions (no subprocess) ────────────────────────────

    if action == "create_app":
        app_name = inquirer.text(
            message="App name:",
            validate=AppNameValidator(),
            style=INQUIRER_STYLE,
        ).execute()
        if scaffolder:
            scaffolder.create_app(app_name)
            show_success("App Created", f"App '{app_name}' created successfully")
            return True
        # No scaffolder — fall back to manage.py startapp
        return await _run_subprocess(
            ["uv", "run", "python", "manage.py", "startapp", app_name],
            cwd=project_path,
            description=f"startapp {app_name}",
        )

    if action == "clear_cache":
        count = 0
        for pycache in project_path.rglob("__pycache__"):
            shutil.rmtree(pycache)
            count += 1
        show_success(
            "Cache Cleared",
            f"Removed {count} __pycache__ director{'ies' if count != 1 else 'y'}",
        )
        return True

    if action == "lint_check":
        return await _run_subprocess(
            ["ruff", "check", "."],
            cwd=project_path,
            description="ruff check",
        )

    # ── Interactive commands (inherit terminal) ─────────────────────

    interactive_actions = {"runserver", "shell", "createsuperuser"}
    if action in interactive_actions:
        return await _run_interactive(action, project_path)

    # ── Non-interactive management commands ─────────────────────────

    return await _run_subprocess(
        ["uv", "run", "python", "manage.py", action],
        cwd=project_path,
        description=f"manage.py {action}",
    )


async def _run_interactive(action: str, project_path: Path) -> bool:
    """Run an interactive command that takes over the terminal.

    Handles ``Ctrl+C`` gracefully so the TUI returns to the menu
    instead of crashing.
    """
    cmd = ["uv", "run", "python", "manage.py", action]
    console.print(f"\n[{Theme.PRIMARY}]{NF.TERMINAL} Starting[/] [bold]{action}[/] ...")
    console.print(f"[{Theme.MUTED}]{'─' * 40}[/]")
    console.print(
        f"[italic {Theme.MUTED}]Press Ctrl+C to stop and return to the menu.[/]"
    )
    console.print()

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=project_path)
        await proc.wait()
    except asyncio.CancelledError:
        # Ctrl+C during start — clean exit
        console.print()
        show_warning("Interrupted", f"{action} was cancelled")
        return True
    except Exception as e:
        show_error("Command Failed", str(e))
        return False

    # If the subprocess received SIGINT (Ctrl+C), returncode = -2
    if proc.returncode in (0, -2):
        console.print()
        show_info("Stopped", f"{action} has stopped")
        return True

    show_error(f"{action} Failed", f"Exit code: {proc.returncode}")
    return False


async def _run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    description: str = "",
    timeout: int = 60,
) -> bool:
    """Run a non-interactive command, capturing and displaying output.

    Shows a transient progress spinner while the command runs, then
    displays the captured stdout or a rich error panel.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        show_error("Not Found", f"Executable not found: {cmd[0]}")
        return False

    # Transient spinner
    with Progress(
        SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
        TextColumn(f"[progress.description]{{task.description}}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"{NF.TERMINAL}  {description or ' '.join(cmd)}...",
            total=None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            progress.stop()
            show_error(
                "Timed Out",
                f"{description or ' '.join(cmd)} did not finish within {timeout}s",
            )
            return False

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode == 0:
            progress.update(
                task,
                description=f"{NF.CHECK}  {description or ' '.join(cmd)} completed",
            )
            if stdout_text:
                # Print output after spinner is cleaned up
                pass  # We print outside the progress context
        else:
            progress.update(
                task,
                description=f"{NF.ERROR}  {description or ' '.join(cmd)} failed (exit {proc.returncode})",
            )
            if stderr_text:
                pass  # We print outside the progress context

    # Print output / errors after progress is gone
    if proc.returncode == 0:
        if stdout_text:
            console.print(f"[{Theme.MUTED}]{stdout_text}[/]")
        return True

    if stderr_text:
        show_error(f"{description or cmd[-1]} Failed", stderr_text)
    else:
        show_error(f"{description or cmd[-1]} Failed", f"Exit code: {proc.returncode}")
    return False


# =============================================================================
# CREATE APPS LOOP
# =============================================================================


def create_apps_loop(scaffolder):
    """Loop for creating multiple Django apps."""
    apps = []

    while True:
        console.print()
        add_app = inquirer.confirm(
            message=f"  {NF.APP}  Create a new Django app?",
            default=False,
            style=INQUIRER_STYLE,
        ).execute()

        if not add_app:
            break

        app_name = inquirer.text(
            message="App name:",
            validate=AppNameValidator(),
            instruction="(lowercase, letters only)",
            style=INQUIRER_STYLE,
        ).execute()

        with Progress(
            SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(f"Creating app '{app_name}'...", total=None)

            if scaffolder.create_app(app_name):
                apps.append(app_name)
                progress.update(
                    task,
                    description=f"{NF.CHECK} App '{app_name}' created!",
                    completed=100,
                )
            else:
                progress.stop()
                show_error("App Creation Failed", f"Could not create app '{app_name}'")

    return apps


# =============================================================================
# COMPLETION PANEL
# =============================================================================


def show_completion(
    project_name: str, db_type: str, github_created: bool, apps: List[str]
):
    """Show completion panel."""
    console.print()
    print_rule("Setup Complete!")
    console.print()

    # Summary table
    summary = Table(box=box.ROUNDED, border_style=Theme.SUCCESS, show_header=False)
    summary.add_column("", style=Theme.ACCENT, width=12)
    summary.add_column("", style=Theme.SUCCESS)

    summary.add_row(f"{NF.DATABASE} Database", db_type.upper())
    summary.add_row(f"{NF.GITHUB} GitHub", "Created" if github_created else "Skipped")
    if apps:
        summary.add_row(f"{NF.APP} Apps", ", ".join(apps))

    panel = Panel(
        summary,
        title=f"  {NF.CHECK_CIRCLE}  Project Created Successfully  {NF.CHECK_CIRCLE}  ",
        title_align="center",
        border_style=Theme.SUCCESS,
    )
    console.print(center(panel, width=70))
    console.print()

    # Next steps
    console.print(f"[bold {Theme.PRIMARY}]Next Steps:[/]")
    console.print()

    steps = Table(box=box.ROUNDED, border_style=Theme.BORDER, show_header=False)
    steps.add_column("", style=Theme.ACCENT, width=4)
    steps.add_column("Command", style=f"bold {Theme.PRIMARY}")
    steps.add_column("Description", style=Theme.MUTED)

    for icon, cmd, desc in [
        (NF.FOLDER, f"cd {project_name}", "Enter project directory"),
        (NF.UV, "uv sync", "Install dependencies"),
        (NF.DATABASE, "uv run manage.py migrate", "Apply migrations"),
        (NF.USER, "uv run manage.py createsuperuser", "Create admin account"),
        (NF.SERVER, "uv run manage.py runserver", "Start development server"),
    ]:
        steps.add_row(f"  {icon}  ", cmd, desc)

    console.print(steps)
    console.print()
    console.print(center(f"[bold {Theme.PRIMARY}]➜ http://127.0.0.1:8000[/]"))
    console.print()


# =============================================================================
# ARGUMENT PARSER
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    In interactive mode (no arguments) the tool shows the full TUI.
    Use ``--version`` to print the version and exit.

    Returns:
        A configured ``ArgumentParser`` instance.
    """
    parser = argparse.ArgumentParser(
        prog="ajo",
        description="Professional Django scaffolder with Cyberpunk TUI",
        epilog="Run without arguments for interactive mode.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Non-interactive mode (requires --name)",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Project name (required with --headless)",
    )
    parser.add_argument(
        "-p",
        "--preset",
        type=str,
        choices=[
            "monolith",
            "rest-api",
            "rest",
            "graphql-api",
            "graphql",
            "docker",
            "fullstack",
        ],
        default="monolith",
        help="Architecture preset (default: monolith)",
    )
    parser.add_argument(
        "-d",
        "--database",
        type=str,
        choices=["sqlite", "postgresql", "mysql"],
        default="sqlite",
        help="Database type (default: sqlite)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Accept all defaults (implies --headless)",
    )
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Skip GitHub setup",
    )
    parser.add_argument(
        "--no-cicd",
        action="store_true",
        help="Skip CI/CD setup",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Parent directory for the project (default: current dir)",
    )
    return parser


# =============================================================================
# HEADLESS EXECUTION
# =============================================================================


async def _headless_execute(args: argparse.Namespace) -> int:
    """Execute the scaffolding pipeline in non-interactive mode.

    Bypasses all TUI prompts and uses provided flags to configure the project.
    Returns 0 on success, 11 on validation error, and 1 on execution failure.
    """
    # 1. Project Name Validation
    project_name = args.name or "myproject"
    is_valid, error_msg = ProjectNameValidator.validate(project_name)
    if not is_valid:
        show_error(
            "Validation Error", f"Invalid project name '{project_name}': {error_msg}"
        )
        return 11

    # 2. Preset Resolution
    preset_aliases = {
        "monolith": "monolith",
        "rest-api": "rest-api",
        "rest": "rest-api",
        "graphql-api": "graphql-api",
        "graphql": "graphql-api",
        "docker": "docker",
        "fullstack": "monolith",
    }
    preset_key = preset_aliases.get(args.preset, "monolith")

    # 3. Database Configuration
    db_configs = {
        "sqlite": {
            "engine": "django.db.backends.sqlite3",
            "name": "db.sqlite3",
            "user": "",
            "password": "",
            "host": "",
            "port": "",
            "packages": [],
        },
        "postgresql": {
            "engine": "django.db.backends.postgresql",
            "name": "postgres",
            "user": "postgres",
            "password": "",
            "host": "localhost",
            "port": "5432",
            "packages": ["psycopg2-binary"],
        },
        "mysql": {
            "engine": "django.db.backends.mysql",
            "name": "mysql",
            "user": "root",
            "password": "",
            "host": "localhost",
            "port": "3306",
            "packages": ["mysqlclient"],
        },
    }
    db_config = db_configs.get(args.database, db_configs["sqlite"])

    # 4. Environment Configuration
    env_config = {
        "project_name": project_name,
        "db_type": args.database,
        "db_config": db_config,
    }

    # 5. Execution
    project_path = args.output_dir / project_name
    console.print(
        f"\n[bold {Theme.PRIMARY}]🚀 Starting headless scaffold for '{project_name}'...[/]"
    )
    console.print(f"  Preset: {preset_key} | Database: {args.database}\n")

    try:
        preset_cls = get_preset(preset_key)
        preset_instance = preset_cls()

        engine = ScaffoldEngine(project_path, env_config=env_config)
        success = await engine.execute(preset=preset_instance)

        if not success:
            show_error(
                "Scaffold Failed", "The scaffolding process was interrupted or failed."
            )
            return 1

        # 6. Completion Summary (Clean output for CI/CD)
        console.print()
        print_rule("Setup Complete", style=Theme.SUCCESS)
        console.print(
            f"  {NF.CHECK}  Project created successfully at: [bold]{project_path}[/]"
        )
        console.print(f"  {NF.CHECK}  Architecture: {preset_instance.name}")
        console.print(f"  {NF.CHECK}  Database: {args.database.upper()}")
        if args.no_github:
            console.print(f"  {NF.INFO}  GitHub setup skipped")
        if args.no_cicd:
            console.print(f"  {NF.INFO}  CI/CD setup skipped")
        console.print()
        console.print(f"[bold {Theme.PRIMARY}]Next steps:[/]")
        console.print(
            f"  cd {project_name} && uv sync && uv run python manage.py migrate"
        )
        console.print()

        return 0

    except PresetError as e:
        show_error("Preset Error", str(e))
        return 1
    except Exception as e:
        show_error("Unexpected Error", str(e))
        return 1


# =============================================================================
# MAIN
# =============================================================================


def _parse_args() -> argparse.Namespace | int | None:
    """Parse and validate CLI arguments.

    Returns:
        - argparse.Namespace: Parsed arguments for normal operation.
        - None: Fast-path action (e.g. --version) taken; exit with code 0.
        - int: Validation error occurred; exit with the returned code.
    """
    parser = build_parser()
    args = parser.parse_args()

    # ── Version fast-path ────────────────────────────────────────────────
    if args.version:
        console.print(f"ajo v{__version__}")
        return None

    # ── Headless mode validation ──────────────────────────────────────────
    if args.headless or args.yes:
        if not args.name and not args.yes:
            show_error("Missing Project Name", "--name is required in headless mode")
            return 11

    return args


@async_entry
async def _async_main() -> int:
    """Async entry point for the ajo-cli.

    Handles both the interactive TUI and the non-interactive headless mode.
    """
    result = _parse_args()
    if result is None:
        return 0  # --version
    if isinstance(result, int):
        return result  # Validation error
    args = result

    # ── Headless / Automated Mode ────────────────────────────────────────
    if args.headless or args.yes:
        return await _headless_execute(args)

    # ── Interactive TUI Mode ─────────────────────────────────────────────
    try:
        # ── Detect Django project once ──────────────────────────────────
        detector = DjangoProjectDetector()

        # ── Dashboard (reactive) ────────────────────────────────────────
        if detector.is_django_project:
            await show_dashboard(detector)
            console.print()

            # ── Smart command menu from SmartDjangoCLI ─────────────────
            smart = SmartDjangoCLI(detector)
            smart_commands = smart.get_commands()
            choices = []
            for cmd in smart_commands:
                urgency = cmd.urgency
                style_tag = command_urgency_style(urgency)
                name_parts = []
                if cmd.icon:
                    name_parts.append(cmd.icon)
                if style_tag:
                    name_parts.append(f"[{style_tag}]{cmd.name}[/]")
                else:
                    name_parts.append(cmd.name)
                name_str = "  ".join(name_parts)
                choices.append(Choice(value=cmd.action, name=f"  {name_str}"))

            choices.append(Separator())
            choices.append(
                Choice(value="new_project", name=f"  {NF.ROCKET}  Create New Project")
            )
            choices.append(Choice(value="exit", name=f"  {NF.ERROR}  Exit"))

            action = inquirer.select(
                message="What would you like to do?",
                choices=choices,
                style=INQUIRER_STYLE,
                qmark=f"{NF.ARROW_RIGHT}",
            ).execute()

            if action == "exit":
                return 0
            elif action == "new_project":
                pass
            else:
                success = await run_command_async(action, Path.cwd())
                return 0 if success else 1

        # New project creation
        console.clear()

        show_features()

        # Project name
        print_rule("Project Setup")
        console.print()

        project_name = inquirer.text(
            message=f"Project name:[/]",
            long_instruction="\n   └── Example: my_blog, awesome-project, django_app",
            validate=lambda x: len(x.strip()) > 0,
            style=INQUIRER_STYLE,
            qmark="",
        ).execute()

        console.print()
        console.print(
            f"  {NF.CHECK}  [{Theme.SUCCESS}]Project:[/] [bold {Theme.PRIMARY}]{project_name}[/]"
        )
        console.print()

        # Architecture preset
        preset = inquirer.select(
            message=f"[bold {Theme.PRIMARY}]{NF.ARROW_RIGHT}  Architecture preset:[/]",
            choices=[
                Choice(
                    value="Standard Monolith",
                    name=f"{NF.STACK} Standard Monolith - Traditional Django",
                ),
                Choice(
                    value="REST API Ready",
                    name=f"{NF.ROCKET} REST API Ready - DRF + CORS",
                ),
            ],
            style=INQUIRER_STYLE,
            qmark="",
            default="Standard Monolith",
        ).execute()

        # Database
        db_type, db_config = select_database()

        # Create project
        with Progress(
            SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style=Theme.PRIMARY, complete_style=Theme.SUCCESS),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(
                f"{NF.DJANGO} Creating Django project...", total=None
            )

            scaffolder = DjangoProjectScaffolder(
                project_name, preset, db_type, db_config
            )
            if not scaffolder.scaffold():
                return 1

            progress.update(task, completed=100)

        # Create apps
        apps = create_apps_loop(scaffolder)

        # GitHub integration
        project_path = Path.cwd() / project_name
        github_created = setup_github(project_path, project_name)

        # CI/CD setup
        if github_created:
            setup_cicd(project_path)

        # Completion
        show_completion(project_name, db_type, github_created, apps)

        return 0

    except KeyboardInterrupt:
        console.print()
        show_warning("Operation Cancelled", "User interrupted the operation")
        return 130
    except AjoError as e:
        show_error("AJO Error", str(e))
        return 1
    except Exception as e:
        show_error("Unexpected Error", str(e))
        console.print(center(f"[italic {Theme.MUTED}]Please report this on GitHub[/]"))
        return 1


def main() -> int:
    """Public sync entry point for ``ajo``.

    Registered in ``pyproject.toml`` as ``ajo = "ajo.cli:main"``.
    Delegates to the async event loop via :func:`_async_main` which
    is wrapped with the :func:`@async_entry <ajo.core.app.async_entry>`
    decorator.
    """
    return _async_main()


if __name__ == "__main__":
    sys.exit(main())
