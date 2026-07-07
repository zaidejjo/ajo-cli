#!/usr/bin/env python3
"""
ajo CLI — Django project scaffolder with a modern TUI.

Run without arguments for interactive mode.
Use ``--help`` to see available options.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import subprocess
import sys
from ctypes import pythonapi
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Local imports (stdlib-only or very lightweight)
from ajo import __version__
from ajo.core.app import async_entry
from ajo.core.color_control import (
    UNSET,
    _Unset,
    configure_console,
    resolve_color_preference,
)
from ajo.core.logging_config import setup_logging
from ajo.core.constants import NF, Theme, ThemeVariant, icon, qmark
from ajo.core.exceptions import AjoError, PresetError

# ── Lightweight stdlib / local imports only at module level ─────────────────
# Rich and InquirerPy are loaded lazily via proxies below so that
# ``import ajo.cli`` stays under 50ms.  See ``LazyImportTracker``.
from ajo.core.lazy_imports import LazyImportTracker, lazy_attr

# =============================================================================
# LAZY PROXIES — Rich & InquirerPy loaded on first use
# =============================================================================
# We keep the same module-level names (``console``, ``inquirer``, ``Panel``,
# etc.) so that every function in this file continues to work unchanged.
# The proxies delay ``import rich`` / ``import InquirerPy`` until they are
# actually accessed.

_all_loaded: bool = False
_no_color_flag: bool | _Unset = UNSET
_color_flag: str | _Unset = UNSET


def _set_color_flags(
    *, no_color: bool | _Unset = UNSET, color: str | _Unset = UNSET
) -> None:
    """Store colour-preference flags so ``_ensure_rich_imported`` can read them.

    Must be called **before** the first access to ``console`` (i.e. before
    :func:`_ensure_rich_imported` triggers).
    """
    global _no_color_flag, _color_flag
    if no_color is not UNSET:
        _no_color_flag = no_color
    if color is not UNSET:
        _color_flag = color


def _ensure_rich_imported() -> None:
    """One-shot import of all Rich and InquirerPy names used in this module.

    Called automatically by every lazy proxy below before the first real
    attribute access.  After the first call all subsequent accesses are
    direct (no proxy overhead)."""
    global _all_loaded
    global inquirer, Choice, Separator, ValidationError, Validator
    global Console, Live, Panel, Spinner
    global Table, Text, Progress, SpinnerColumn, TextColumn
    global BarColumn, TimeElapsedColumn, box, Align, Rule, escape
    global INQUIRER_STYLE, console
    global FileTreePreview, ThemeEngine
    global command_urgency_style, migration_label, ruff_label
    global server_label, state_label, venv_label
    global DjangoProjectDetector, SmartDjangoCLI, SmartCommand
    global check_uv_installed
    global get_preset, list_presets
    global ScaffoldEngine
    global DjangoProjectScaffolder
    global ProjectNameValidator, AppNameValidator
    global _async_entry

    if _all_loaded:
        return

    # Rich
    RichConsole = lazy_attr("rich.console", "Console")
    Console = RichConsole
    Live = lazy_attr("rich.live", "Live")
    Panel = lazy_attr("rich.panel", "Panel")
    Spinner = lazy_attr("rich.spinner", "Spinner")
    Table = lazy_attr("rich.table", "Table")
    Text = lazy_attr("rich.text", "Text")
    Progress = lazy_attr("rich.progress", "Progress")
    SpinnerColumn = lazy_attr("rich.progress", "SpinnerColumn")
    TextColumn = lazy_attr("rich.progress", "TextColumn")
    BarColumn = lazy_attr("rich.progress", "BarColumn")
    TimeElapsedColumn = lazy_attr("rich.progress", "TimeElapsedColumn")
    box = lazy_attr("rich", "box")
    Align = lazy_attr("rich.align", "Align")
    Rule = lazy_attr("rich.rule", "Rule")
    escape = lazy_attr("rich.markup", "escape")

    # InquirerPy
    import InquirerPy.inquirer as inquirer

    Choice = lazy_attr("InquirerPy.base.control", "Choice")
    Separator = lazy_attr("InquirerPy.separator", "Separator")
    ValidationError = lazy_attr("InquirerPy.validator", "ValidationError")
    Validator = lazy_attr("InquirerPy.validator", "Validator")

    # Local (trigger theme / engine imports)
    from ajo.ui.theme import (
        INQUIRER_STYLE as _IS,
    )
    from ajo.ui.theme import (
        FileTreePreview as _FTP,
    )
    from ajo.ui.theme import (
        ThemeEngine as _TE,
    )
    from ajo.ui.theme import (
        command_urgency_style as _cus,
    )
    from ajo.ui.theme import (
        migration_label as _ml,
    )
    from ajo.ui.theme import (
        ruff_label as _rl,
    )
    from ajo.ui.theme import (
        server_label as _sl,
    )
    from ajo.ui.theme import (
        state_label as _sl2,
    )
    from ajo.ui.theme import (
        venv_label as _vl,
    )

    INQUIRER_STYLE = _IS
    FileTreePreview = _FTP
    ThemeEngine = _TE
    command_urgency_style = _cus
    migration_label = _ml
    ruff_label = _rl
    server_label = _sl
    state_label = _sl2
    venv_label = _vl

    from ajo.detector import DjangoProjectDetector as _DPD
    from ajo.detector import SmartDjangoCLI as _SDC
    from ajo.detector.prereqs import check_uv_installed as _cui
    from ajo.presets import get_preset as _gp
    from ajo.presets import list_presets as _lp
    from ajo.scaffolding import ScaffoldEngine as _SE
    from ajo.templates.django_app import DjangoProjectScaffolder as _DPS
    from ajo.validators import ProjectNameValidator as _PNV

    DjangoProjectDetector = _DPD
    SmartDjangoCLI = _SDC
    check_uv_installed = _cui
    get_preset = _gp
    list_presets = _lp
    ScaffoldEngine = _SE
    DjangoProjectScaffolder = _DPS
    ProjectNameValidator = _PNV

    # ── AppNameValidator (depends on InquirerPy Validator) ─────────
    class _AppNameValidator(Validator):  # type: ignore[valid-type]
        """Django app name validation."""

        PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
        RESERVED = {"django", "test", "tests", "site", "admin", "config", "settings"}

        def validate(self, document: Any) -> bool:  # type: ignore[override]
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

    global AppNameValidator
    AppNameValidator = _AppNameValidator

    # Global console (respects NO_COLOR / FORCE_COLOR / --no-color)
    global _no_color_flag, _color_flag
    console = configure_console(no_color=_no_color_flag, color=_color_flag)
    _all_loaded = True


# ── Module-level replacements that trigger lazy loading ──────────────────


class _LazyConsole:
    """Proxy that calls ``_ensure_rich_imported()`` on first attribute access.

    This lets us keep ``console.print(...)`` syntax unchanged.
    """

    _instance: Any = None

    def __getattr__(self, name: str) -> Any:
        if self._instance is None:
            _ensure_rich_imported()
            # After _ensure_rich_imported, the module-level ``console`` is
            # replaced, so this proxy should never be called again.
            # But just in case, delegate to the real console:
            import sys as _sys

            mod = _sys.modules[__name__]
            self._instance = getattr(mod, "console", None)
            if self._instance is None or self._instance is self:
                raise RuntimeError("Lazy console not initialised")
        return getattr(self._instance, name)


# Module-level names initialised to lazy proxies.
# After ``_ensure_rich_imported()`` these are overwritten with real objects.
console: Any = _LazyConsole()
inquirer: Any = None
Choice: Any = None
Separator: Any = None
ValidationError: Any = None
Validator: Any = None

Console: Any = None
Live: Any = None
Panel: Any = None
Spinner: Any = None
Table: Any = None
Text: Any = None
Progress: Any = None
SpinnerColumn: Any = None
TextColumn: Any = None
BarColumn: Any = None
TimeElapsedColumn: Any = None
box: Any = None
Align: Any = None
Rule: Any = None

INQUIRER_STYLE: Any = None
FileTreePreview: Any = None
ThemeEngine: Any = None
command_urgency_style: Any = None
migration_label: Any = None
ruff_label: Any = None
server_label: Any = None
state_label: Any = None
venv_label: Any = None

DjangoProjectDetector: Any = None
SmartDjangoCLI: Any = None
check_uv_installed: Any = None
get_preset: Any = None
list_presets: Any = None
ScaffoldEngine: Any = None
DjangoProjectScaffolder: Any = None
ProjectNameValidator: Any = None


# =============================================================================
# UI FUNCTIONS
# =============================================================================


def center(content, width: Optional[int] = None):
    """Center content on screen."""
    return Align.center(content, width=width)


def print_rule(title: str = "", style: str = Theme.MUTED):
    """Print a horizontal rule with optional title."""
    console.print(Rule(title=title, style=f"dim {style}"))


def print_banner():
    """Display a clean, minimal header banner."""
    from ajo import __version__

    console.print()
    console.print(Rule(style=f"dim {Theme.MUTED}"))
    console.print(
        f"  [bold {Theme.PRIMARY}]ajo[/]  [dim {Theme.MUTED}]v{__version__}[/]"
        f"  —  [italic {Theme.SECONDARY}]Django Scaffolder[/]"
    )
    console.print(
        f"  [{Theme.SUCCESS}]{NF.PYTHON} Python 3.10+[/]"
        f"  [{Theme.PRIMARY}]{NF.DJANGO} Django 5.0+[/]"
        f"  [{Theme.SECONDARY}]{NF.UV} uv[/]"
        f"  [{Theme.ACCENT}]{NF.RUFF} Ruff[/]"
    )
    console.print(Rule(style=f"dim {Theme.MUTED}"))
    console.print()


def show_error(title: str, message: str, suggestion: Optional[str] = None):
    """Display error message without nested panels."""
    err_icon = icon("error")
    bullet = icon("bullet")
    console.print(
        f"  [{Theme.ERROR}]{err_icon}[/] [bold {Theme.ERROR}]{escape(title)}[/]"
    )
    console.print(f"    [{Theme.ERROR}]{escape(message)}[/]")
    if suggestion:
        console.print(
            f"    [dim {Theme.MUTED}]{bullet}[/] [italic {Theme.WARNING}]{escape(suggestion)}[/]"
        )
    console.print()


def show_success(title: str, message: str):
    """Display success message without nested panels."""
    check = icon("check")
    console.print(
        f"  [{Theme.SUCCESS}]{check}[/] [bold {Theme.SUCCESS}]{escape(title)}[/]"
    )
    console.print(f"    [{Theme.SUCCESS}]{escape(message)}[/]")
    console.print()


def show_info(title: str, message: str):
    """Display info message without nested panels."""
    info_glyph = icon("info")
    console.print(
        f"  [{Theme.PRIMARY}]{info_glyph}[/] [bold {Theme.PRIMARY}]{escape(title)}[/]"
    )
    console.print(f"    [{Theme.MUTED}]{escape(message)}[/]")
    console.print()


def show_warning(title: str, message: str):
    """Display warning message without nested panels."""
    warn_glyph = icon("warning")
    console.print(
        f"  [{Theme.WARNING}]{warn_glyph}[/] [bold {Theme.WARNING}]{escape(title)}[/]"
    )
    console.print(f"    [{Theme.WARNING}]{escape(message)}[/]")
    console.print()


# =============================================================================
# FEATURE GRID
# =============================================================================


def show_features():
    """Display feature overview with a clean, minimal layout."""
    console.print()
    print_rule("Features")
    console.print()

    features = [
        ("Multi-Database Support", "PostgreSQL, MySQL, SQLite"),
        ("GitHub Integration", "Auto repo creation & push"),
        ("CI/CD with Ruff", "GitHub Actions pipeline"),
        (".env Security", "Auto-generated secrets"),
        ("Multiple Apps", "Scaffold any number of apps"),
        ("Testing", "pytest with coverage"),
        ("Docker Support", "Dockerfile + compose"),
        ("Bootstrap 5 Themes", "Pre-built UI themes"),
        ("Django Shell Plus", "Enhanced shell"),
        ("Debug Toolbar", "Dev debugging tools"),
    ]

    bullet = icon("bullet")
    plus = icon("plus")
    for i in range(0, len(features), 2):
        left_name, left_desc = features[i]
        line = f"  [{Theme.PRIMARY}]{bullet}[/] [bold]{left_name}[/]  [dim {Theme.MUTED}]— {left_desc}[/]"
        if i + 1 < len(features):
            right_name, right_desc = features[i + 1]
            padding = " " * max(1, 52 - len(left_name) - len(left_desc))
            line += f"{padding}[{Theme.PRIMARY}]{bullet}[/] [bold]{right_name}[/]  [dim {Theme.MUTED}]— {right_desc}[/]"
        console.print(line)

    console.print()
    print_rule("Architecture Presets")
    console.print()

    presets = [
        (
            "Standard Monolith",
            "Traditional Django + templates",
            "HTML + Bootstrap 5 + HTMX",
        ),
        ("REST API Ready", "DRF + CORS pre-configured", "DRF + JWT + Swagger"),
        ("Ninja API", "django-ninja auto-generated API", "Swagger UI + Schemas"),
        ("GraphQL API", "Graphene + Django", "GraphiQL + Relay"),
        ("Full-Stack Modern", "Django + React / Vue / Alpine", "REST API + Frontend"),
    ]
    for name, desc, comps in presets:
        console.print(f"  [{Theme.ACCENT}]{bullet}[/] [bold]{name}[/]")
        console.print(
            f"    [dim {Theme.MUTED}]{desc}[/]  —  [{Theme.SECONDARY}]{comps}[/]"
        )
    console.print()

    print_rule("Add-on Modules")
    console.print()

    addons_list = [
        ("Auth & Users", "JWT + registration + profile API"),
        ("Caching & Performance", "Redis + connection pooling"),
        ("Security Hardening", "Axes + 2FA + CSP headers"),
        ("Testing Infrastructure", "pytest + coverage + factories"),
    ]
    for i in range(0, len(addons_list), 2):
        left_name, left_desc = addons_list[i]
        line = f"  [{Theme.ACCENT}]{plus}[/] [bold]{left_name}[/]  [dim {Theme.MUTED}]— {left_desc}[/]"
        if i + 1 < len(addons_list):
            right_name, right_desc = addons_list[i + 1]
            padding = " " * max(1, 46 - len(left_name) - len(left_desc))
            line += f"{padding}[{Theme.ACCENT}]{plus}[/] [bold]{right_name}[/]  [dim {Theme.MUTED}]— {right_desc}[/]"
        console.print(line)
    console.print()


# =============================================================================
# PREREQUISITES CHECK
# =============================================================================


def check_prerequisites() -> bool:
    """Check system prerequisites."""
    bullet = icon("bullet")
    print_rule("System Prerequisites")
    console.print()

    all_ok = True

    # Python
    py_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    console.print(
        f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]Python 3.10+[/]  [dim {Theme.MUTED}]v{py_version}[/]"
    )

    # uv
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        uv_ok = result.returncode == 0
        uv_version = result.stdout.strip().split()[-1] if uv_ok else "Not found"
        if uv_ok:
            console.print(
                f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]uv[/]  [dim {Theme.MUTED}]{uv_version}[/]"
            )
        else:
            console.print(
                f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.ERROR}]uv[/]  [dim {Theme.MUTED}]Not installed[/]"
            )
            all_ok = False
    except FileNotFoundError:
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.ERROR}]uv[/]  [dim {Theme.MUTED}]Not installed[/]"
        )
        all_ok = False

    # Git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        git_version = (
            result.stdout.strip().split()[-1] if result.returncode == 0 else "Not found"
        )
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]Git[/]  [dim {Theme.MUTED}]{git_version}[/]"
        )
    except FileNotFoundError:
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] [dim {Theme.MUTED}]Git[/]  Not installed (optional)"
        )

    # GitHub CLI
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            gh_version = result.stdout.strip().split()[2]
            console.print(
                f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]GitHub CLI[/]  [dim {Theme.MUTED}]{gh_version}[/]"
            )
        else:
            console.print(
                f"  [dim {Theme.MUTED}]{bullet}[/] [dim {Theme.MUTED}]GitHub CLI[/]  Not installed (optional)"
            )
    except FileNotFoundError:
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] [dim {Theme.MUTED}]GitHub CLI[/]  Not installed (optional)"
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
    bullet = icon("bullet")
    console.print()
    print_rule("Database Configuration")
    console.print()

    console.print(
        f"  [dim {Theme.MUTED}]{bullet}[/] [bold {Theme.PRIMARY}]SQLite[/]        [dim {Theme.MUTED}]— Lightweight, file-based (default)[/]"
    )
    console.print(
        f"  [dim {Theme.MUTED}]{bullet}[/] [bold {Theme.PRIMARY}]PostgreSQL[/]    [dim {Theme.MUTED}]— Production-ready, feature-rich[/]"
    )
    console.print(
        f"  [dim {Theme.MUTED}]{bullet}[/] [bold {Theme.PRIMARY}]MySQL[/]         [dim {Theme.MUTED}]— Popular, reliable[/]"
    )
    console.print()

    db_choice = inquirer.select(
        message="Select your database:",
        choices=[
            Choice(value="sqlite", name="SQLite — Development"),
            Choice(value="postgresql", name="PostgreSQL — Production"),
            Choice(value="mysql", name="MySQL — Production"),
        ],
        style=INQUIRER_STYLE,
        qmark=qmark(),
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
        message="Create a GitHub repository?",
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
            Choice(value="public", name="Public — Anyone can see"),
            Choice(value="private", name="Private — Only you"),
        ],
        style=INQUIRER_STYLE,
    ).execute()

    with Progress(
        SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Creating repository...", total=None)

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
            progress.update(task, description="Repository created", completed=100)
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
        message="Setup CI/CD with GitHub Actions?",
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
        rocket = "󰑣"
        branch = ""
        python = ""
        info = self._detector.project_info
        table = Table(
            box=box.SIMPLE, border_style=Theme.MUTED, show_header=False, padding=(0, 1)
        )
        table.add_column("", style=Theme.ACCENT, width=18)
        table.add_column("", style=Theme.PRIMARY)

        # ── Project Meta ─────────────────────────────────────────────
        table.add_row(f"{rocket} Project", str(info.get("project_name", "Unknown")))
        table.add_row(f"{branch} Branch", str(info.get("git_branch", "N/A")))
        table.add_row(
            f"{python} Virtual env", venv_label(info.get("venv_active", False))
        )

        table.add_row("", "")  # visual spacer

        # ── Live Status ──────────────────────────────────────────────
        table.add_row("[dim]Server[/]", server_label(info.get("server_running", False)))
        table.add_row("[dim]Apps[/]", str(len(info.get("apps", []))))
        table.add_row("[dim]Models[/]", str(info.get("models_count", 0)))

        # ── Migrations (spinner until slow scan) ─────────────────────
        if self._slow_loaded:
            needs_mig = info.get("needs_migrations", False)
            unapplied = len(info.get("unapplied_migrations", []))
            table.add_row("[dim]Migrations[/]", migration_label(needs_mig, unapplied))
        else:
            table.add_row("[dim]Migrations[/]", self._spinner_mig)

        # ── Ruff lint status (spinner until slow scan) ───────────────
        ruff = info.get("ruff_result")
        if self._slow_loaded:
            exit_code = ruff.exit_code if ruff else None
            line_count = ruff.line_count if ruff else 0
            table.add_row("[dim]Ruff[/]", ruff_label(exit_code, line_count))
        else:
            table.add_row("[dim]Ruff[/]", self._spinner_ruff)

        return Panel(
            table,
            title=" Django Project ",
            title_align="left",
            border_style=Theme.MUTED,
            padding=(0, 1),
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
# DIAGNOSTIC DASHBOARD
# =============================================================================


async def show_diagnostics(detector: DjangoProjectDetector) -> None:
    """Run the self-healing diagnostic engine and display issues.

    Uses :class:`~ajo.validators.DiagnosticEngine` to scan the project
    for common misconfigurations.  For each discoverable issue the user
    is offered an **Auto-Fix** option.

    Args:
        detector: An initialised :class:`DjangoProjectDetector` whose
            ``path`` attribute points to the project root.
    """
    # Lazy import for startup performance
    from ajo.validators import DiagnosticEngine

    engine = DiagnosticEngine(detector.path)
    issues = engine.run_full_diagnostic()

    if not issues:
        show_success("System Healthy", "No issues detected")
        return

    console.print()
    print_rule(f"Diagnostics ({len(issues)} issue{'s' if len(issues) != 1 else ''})")
    console.print()

    for i, issue in enumerate(issues, 1):
        color = (
            Theme.ERROR
            if issue.severity == "error"
            else (Theme.WARNING if issue.severity == "warning" else Theme.PRIMARY)
        )
        label = issue.severity.upper()

        console.print(f"  {i:2d}. [{color}][{label}][/]  {issue.message}")

        if issue.auto_fix and issue.fix_description:
            from InquirerPy import inquirer as _diag_inquirer

            fix = _diag_inquirer.confirm(
                message=f"     Auto-fix: {issue.fix_description}?",
                default=True,
                style=INQUIRER_STYLE,
            ).execute()

            if fix:
                success = issue.auto_fix()
                if success:
                    show_success("Fixed", issue.fix_description)
                else:
                    show_error("Fix Failed", f"Could not {issue.fix_description}")

    console.print()
    show_info(
        "Diagnostics Complete",
        f"Resolved {sum(1 for i in issues if i.auto_fix)} issue(s). "
        f"Run diagnostics again to re-check.",
    )


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
    console.print(f"\n[{Theme.PRIMARY}]Starting[/] [bold]{action}[/] ...")
    console.print(f"[dim {Theme.MUTED}]{'─' * 40}[/]")
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
            f"{description or ' '.join(cmd)}...",
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
                description=f"{description or ' '.join(cmd)} completed",
            )
        else:
            progress.update(
                task,
                description=f"{description or ' '.join(cmd)} failed (exit {proc.returncode})",
            )

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
            message="Create a new Django app?",
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

        # Check if the app directory already exists
        app_path = scaffolder.root_path / app_name
        if app_path.exists():
            console.print(
                f"  [dim {Theme.MUTED}]{icon('bullet')}[/] App '{app_name}' already exists. Skipping creation."
            )
            continue

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
                    description=f"App '{app_name}' created",
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
    """Show completion summary with next steps."""
    bullet = icon("bullet")
    check = icon("check")
    db_icon = icon("database")
    console.print()
    print_rule("Setup Complete!")
    console.print()

    console.print(
        f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]Database:[/]  "
        f"{db_icon} [bold]{db_type.upper()}[/]"
    )
    gh_status = f"{check} Created" if github_created else f"{icon('error')} Skipped"
    console.print(
        f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]GitHub:[/]    {gh_status}"
    )
    if apps:
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] [{Theme.SUCCESS}]Apps:[/]      {', '.join(apps)}"
        )
    console.print()

    # Next steps
    print_rule("Next Steps")
    console.print()
    steps = [
        (f"cd {project_name}", "Enter project directory"),
        ("uv sync", "Install dependencies"),
        ("uv run manage.py migrate", "Apply migrations"),
        ("uv run manage.py createsuperuser", "Create admin account"),
        ("uv run manage.py runserver", "Start development server"),
    ]
    for cmd, desc in steps:
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] [bold {Theme.PRIMARY}]{cmd}[/]"
        )
        console.print(f"    [dim {Theme.MUTED}]{desc}[/]")
    console.print()
    console.print(f"  [bold {Theme.PRIMARY}]➜ http://127.0.0.1:8000[/]")
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

    # ── Subcommands (doctor, completion, …) ──────────────────────────────
    # When a subcommand is given (e.g. ``ajo doctor``), ``args.command``
    # is set to the subcommand name.  When omitted, ``args.command`` is
    # ``None`` and the existing interactive / headless behaviour applies.
    subparsers = parser.add_subparsers(dest="command")

    # ``ajo doctor`` — system health check
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="System health check",
        description="Check all system prerequisites, configuration, and terminal capabilities.",
    )
    doctor_parser.set_defaults(command="doctor")

    # ``ajo completion <shell>`` — generate shell completions (placeholder)
    completion_parser = subparsers.add_parser(
        "completion",
        help="Generate shell completions",
        description="Generate shell completion scripts for bash, zsh, or tcsh.",
    )
    completion_parser.add_argument(
        "shell",
        type=str,
        choices=["bash", "zsh", "tcsh"],
        help="Target shell (supported: bash, zsh, tcsh)",
    )
    completion_parser.set_defaults(command="completion")

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
            "ninja-api",
            "ninja",
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
    parser.add_argument(
        "--theme",
        type=str,
        choices=["cyberpunk", "dracula", "monochromatic", "mono"],
        default="cyberpunk",
        help="Visual theme (default: cyberpunk)",
    )
    parser.add_argument(
        "--addons",
        type=str,
        nargs="*",
        default=None,
        help="Add-on modules to include (e.g. auth cache security testing)",
    )
    parser.add_argument(
        "--no-addons",
        action="store_true",
        dest="no_addons",
        help="Skip all add-on modules",
    )
    # ── Colour / ANSI control ────────────────────────────────────────────
    parser.add_argument(
        "--no-color",
        action="store_true",
        dest="no_color",
        default=False,
        help="Disable ANSI colour output (also honours NO_COLOR env var)",
    )
    parser.add_argument(
        "--color",
        type=str,
        choices=["auto", "always", "never"],
        default="auto",
        help="When to use ANSI colours (default: auto)",
    )
    # ── Verbosity / Logging ───────────────────────────────────────────────
    parser.add_argument(
        "-v",
        action="count",
        dest="verbosity",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        dest="verbosity",
        const=-1,
        help="Suppress non-error output (sets log level to ERROR)",
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
        "ninja-api": "ninja-api",
        "ninja": "ninja-api",
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
        "preset_key": preset_key,
    }

    # 5. Add-on Resolution
    addons: list[Any] | None = None
    if args.no_addons:
        addons = None
    elif args.addons is not None:
        from ajo.presets.addons import resolve_addons

        try:
            addons = resolve_addons(args.addons, preset_key=preset_key)
        except PresetError as e:
            show_error("Add-on Error", str(e))
            return 1
    # If neither --addons nor --no-addons is specified, prompt in headless
    # only when --yes is not set (interactive headless).  When --yes is set
    # we skip addons entirely to maintain a fully-automated flow.
    elif not args.yes:
        from ajo.presets.addons import get_addon_choices

        choices = get_addon_choices(preset_key=preset_key)
        if choices:
            console.print()
            print_rule("Add-on Modules")
            console.print()
            console.print(
                f"  [dim {Theme.MUTED}]Extra feature modules to layer on top of the preset.[/]"
            )
            console.print(
                f"  [dim {Theme.MUTED}]Available: {', '.join(sorted(choices))}[/]"
            )
            console.print()

    # 6. Execution
    project_path = args.output_dir / project_name
    console.print(
        f"\n[bold {Theme.PRIMARY}]Starting headless scaffold for '{project_name}'...[/]"
    )
    console.print(f"  Preset: {preset_key} | Database: {args.database}")
    if addons:
        console.print(f"  Add-ons: {', '.join(a.name for a in addons)}")
    console.print()

    try:
        preset_cls = get_preset(preset_key)
        preset_instance = preset_cls()

        engine = ScaffoldEngine(project_path, env_config=env_config)
        success = await engine.execute(preset=preset_instance, addons=addons)

        if not success:
            show_error(
                "Scaffold Failed", "The scaffolding process was interrupted or failed."
            )
            return 1

        # 7. Completion Summary (Clean output for CI/CD)
        console.print()
        bullet = icon("bullet")
        print_rule("Setup Complete", style=Theme.SUCCESS)
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] Project created at: [bold]{project_path}[/]"
        )
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] Architecture: {preset_instance.name}"
        )
        console.print(
            f"  [dim {Theme.MUTED}]{bullet}[/] Database: {args.database.upper()}"
        )
        if addons:
            console.print(
                f"  [dim {Theme.MUTED}]{bullet}[/] Add-ons: {', '.join(a.name for a in addons)}"
            )
        if args.no_github:
            console.print(f"  [dim {Theme.MUTED}]{bullet}[/] GitHub setup: skipped")
        if args.no_cicd:
            console.print(f"  [dim {Theme.MUTED}]{bullet}[/] CI/CD setup: skipped")
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
    # Use raw ``print()`` here — Rich console is NOT loaded at this point
    # when running --version or --help, ensuring startup stays under 50ms.
    if args.version:
        print(f"ajo v{__version__}")
        return None

    # ── Apply colour-preference flags BEFORE lazy imports ──────────────
    # This ensures the Console is created with the correct settings.
    _set_color_flags(no_color=args.no_color, color=args.color)

    # ── Configure logging from verbosity flags ──────────────────────────
    setup_logging(verbosity=args.verbosity)

    # ── Ensure lazy (Rich / InquirerPy) imports are loaded ──────────────
    # From this point forward, all module-level names (console, inquirer,
    # Panel, ThemeEngine, etc.) will have their real values.
    # This call is idempotent and costs ~0 after the first invocation.
    _ensure_rich_imported()

    # ── Headless mode validation (only when no subcommand) ────────────────
    if not args.command and (args.headless or args.yes):
        if not args.name and not args.yes:
            show_error("Missing Project Name", "--name is required in headless mode")
            return 11

    return args


@async_entry
async def _async_main() -> int:
    """Async entry point for the ajo-cli.

    Handles both the interactive TUI and the non-interactive headless mode.
    """
    rocket = icon("rocket")
    dj = icon("django")
    api = icon("󱂛")
    ninja = icon("󰝴")

    result = _parse_args()
    if result is None:
        return 0  # --version
    if isinstance(result, int):
        return result  # Validation error
    args = result

    # ── Subcommand dispatch (doctor, completion, …) ───────────────────────
    if args.command is not None:
        if args.command == "doctor":
            from ajo.commands.doctor import run as run_doctor

            return run_doctor(args)
        if args.command == "completion":
            try:
                from ajo.commands.completions import run as run_completion

                return run_completion(args)
            except ImportError:
                console.print(
                    "[bold red]Error:[/] Shell completions support is not installed. "
                    "Run [bold]uv add shtab[/] and try again."
                )
                return 1
        # Unknown subcommand — should not happen with argparse, but safeguard
        console.print(f"[bold red]Error:[/] Unknown command: {args.command}")
        return 2

    # ── Theme Engine initialisation ──────────────────────────────────────
    engine = ThemeEngine.get_instance()
    engine.set_theme(ThemeVariant.from_string(args.theme))
    engine.adapt_to_depth()
    # Rebuild INQUIRER_STYLE from the active theme
    global INQUIRER_STYLE
    INQUIRER_STYLE = engine.get_inquirer_style()

    # ── Config initialisation ────────────────────────────────────────────
    from ajo.core.config import ConfigManager

    config = ConfigManager()

    # ── First-time Nerd Font prompt (interactive only) ───────────────────
    if config.is_first_run() and not (args.headless or args.yes):
        console.print()
        nerd_font = inquirer.confirm(
            message="Do you use a Nerd Font in your terminal?",
            default=False,
            style=INQUIRER_STYLE,
            qmark="?",
        ).execute()
        config.set("nerd_fonts", nerd_font, auto_save=True)

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
                if style_tag:
                    name_str = f"  [{style_tag}]{cmd.name}[/]"
                else:
                    name_str = f"  {cmd.name}"
                choices.append(Choice(value=cmd.action, name=name_str))

            choices.append(Separator())
            choices.append(
                Choice(
                    value="diagnostics",
                    name="  Run Diagnostics",
                )
            )
            choices.append(Choice(value="new_project", name="  Create New Project"))
            choices.append(Choice(value="exit", name="  Exit"))

            action = inquirer.select(
                message="What would you like to do?",
                choices=choices,
                style=INQUIRER_STYLE,
                qmark=qmark(),
            ).execute()

            if action == "exit":
                return 0
            elif action == "new_project":
                pass
            elif action == "diagnostics":
                await show_diagnostics(detector)
                return 0
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
            message=f"{rocket} Project name:[/]",
            long_instruction="\n   └── Example: my_blog, awesome-project, django_app",
            validate=lambda x: len(x.strip()) > 0,
            style=INQUIRER_STYLE,
            qmark="",
        ).execute()

        console.print()
        console.print(
            f"  [dim {Theme.MUTED}]{icon('bullet')}[/] [{Theme.SUCCESS}]Project:[/] [bold {Theme.PRIMARY}]{project_name}[/]"
        )
        console.print()

        # Architecture preset
        preset = inquirer.select(
            message="Architecture preset:",
            choices=[
                Choice(
                    value="Standard Monolith",
                    name=f" {dj} Standard Monolith — Traditional Django",
                ),
                Choice(
                    value="REST API Ready",
                    name=f"{api} {dj} REST API Ready — DRF + CORS + Swagger",
                ),
                Choice(
                    value="Ninja API",
                    name=f"{ninja} {dj} Ninja API — django-ninja + Swagger UI",
                ),
            ],
            style=INQUIRER_STYLE,
            qmark="",
            default="Standard Monolith",
        ).execute()

        # Database
        db_type, db_config = select_database()

        # ── Add-on modules selection ─────────────────────────────────────
        from ajo.presets.addons import get_addon_choices as _get_addon_choices
        from ajo.presets.addons import resolve_addons as _resolve_addons

        _preset_key = "monolith"
        if preset == "REST API Ready":
            _preset_key = "rest-api"
        elif preset == "Ninja API":
            _preset_key = "ninja-api"

        _addon_choices = _get_addon_choices(preset_key=_preset_key)
        _selected_addon_keys: list[str] = []
        _addon_instances: list[Any] = []
        if _addon_choices:
            console.print()
            print_rule("Add-on Modules")
            console.print()
            console.print(
                f"  [dim {Theme.MUTED}]Optional feature modules to layer on your project.[/]"
            )
            console.print()

            _choice_objects = [
                Choice(
                    value=key,
                    name=f"  {info['name']}  [dim {Theme.MUTED}]— {info['description']}[/]",
                )
                for key, info in _addon_choices.items()
            ]
            _selected_addon_keys = inquirer.checkbox(
                message="Select add-on modules (space to toggle):",
                choices=_choice_objects,
                style=INQUIRER_STYLE,
                qmark=qmark(),
                cycle=False,
            ).execute()

        # ── Scaffold preview ────────────────────────────────────────────
        from ajo.presets import get_preset as _get_preset

        console.print()
        print_rule("Scaffold Preview")
        console.print()

        _preset_cls = _get_preset(_preset_key)
        _preset_instance = _preset_cls()

        _preview_files: list[tuple[str, int]] = [
            (f"{project_name}/", 0),
            (f"{project_name}/.env", 512),
            (f"{project_name}/.gitignore", 256),
            (f"{project_name}/pyproject.toml", 1024),
        ]

        for _rel_path, _size in _preset_instance.preview_files:
            _preview_files.append((f"{project_name}/{_rel_path}", _size))

        # Add add-on preview files
        if _selected_addon_keys:
            _addon_instances = _resolve_addons(
                _selected_addon_keys, preset_key=_preset_key
            )
            for _addon in _addon_instances:
                _addon_files = getattr(_addon, "preview_files", None)
                if _addon_files is not None:
                    for _rel_path, _size in _addon_files:
                        _preview_files.append((f"{project_name}/{_rel_path}", _size))

        preview = FileTreePreview()
        tree = preview.build(_preview_files, title="Files to be created")
        console.print(tree)
        console.print()

        confirm = inquirer.confirm(
            message="Proceed with scaffold?",
            default=True,
            style=INQUIRER_STYLE,
        ).execute()

        if not confirm:
            show_warning("Cancelled", "Scaffold cancelled by user")
            return 0

        # Create project
        with Progress(
            SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style=Theme.PRIMARY, complete_style=Theme.SUCCESS),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Creating Django project...", total=None)

            scaffolder = DjangoProjectScaffolder(
                project_name, preset, db_type, db_config
            )
            if not scaffolder.scaffold():
                return 1

            progress.update(task, completed=100)

        # ── Apply add-on modules ──────────────────────────────────────────
        if _selected_addon_keys:
            project_path = Path.cwd() / project_name
            env_config = {
                "project_name": project_name,
                "db_type": db_type,
                "db_config": db_config,
                "preset_key": _preset_key,
            }
            with Progress(
                SpinnerColumn("dots12", style=f"bold {Theme.PRIMARY}"),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=False,
            ) as _addon_progress:
                _addon_task = _addon_progress.add_task(
                    "Applying add-on modules...", total=None
                )
                for _addon in _addon_instances:
                    try:
                        await _addon.apply(project_path, project_name, env_config)
                    except PresetError as e:
                        show_error("Add-on Error", str(e))
                        return 1
                    except Exception as e:
                        show_error(
                            f"Add-on '{_addon.name}' Error",
                            str(e),
                        )
                        return 1
                _addon_progress.update(
                    _addon_task,
                    description="Add-on modules applied",
                    completed=100,
                )

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
        if _selected_addon_keys:
            console.print(
                f"  [dim {Theme.MUTED}]{icon('bullet')}[/] [{Theme.ACCENT}]Add-ons:[/]   "
                f"{', '.join(a.name for a in _addon_instances)}"
            )
            console.print()

        return 0

    except KeyboardInterrupt:
        console.print()
        show_warning("Operation Cancelled", "User interrupted the operation")
        return 130
    except AjoError as e:
        show_error("AJO Error", str(e))
        return 1
    except Exception as e:
        import traceback

        traceback.print_exc()
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
