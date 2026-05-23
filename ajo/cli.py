#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         AJO CLI - Professional Django Scaffolder              ║
║                         Cyberpunk Edition · Enterprise Ready                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import re
import subprocess
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

try:
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from InquirerPy.validator import ValidationError, Validator
    from InquirerPy.utils import get_style as get_inquirer_style
except ImportError:
    print("❌ InquirerPy not installed. Run: uv pip install InquirerPy")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
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
    from rich.columns import Columns
    from rich.padding import Padding
    from rich.rule import Rule
except ImportError:
    print("❌ Rich not installed. Run: uv pip install rich")
    sys.exit(1)

# Local imports
from ajo.templates.django_app import DjangoProjectScaffolder
from ajo.validators import ProjectNameValidator
from ajo.utils import check_uv_installed, get_uv_version
from ajo.exceptions import AJOError
from ajo.detector import DjangoProjectDetector

# Global console
console = Console()

# =============================================================================
# NERD FONT ICONS - Complete Set
# =============================================================================


class NF:
    """Nerd Font icons for professional TUI."""

    # Brand & Tech
    PYTHON = ""
    DJANGO = "󰌾"
    UV = "󱑍"
    RUFF = "󱘗"
    GIT = "󰊢"
    GITHUB = "󰊤"
    DOCKER = "󰡨"

    # Database
    DATABASE = "󰆼"
    SQLITE = "󰌾"
    POSTGRES = ""
    MYSQL = ""

    # UI Elements
    ARROW_RIGHT = "󰁔"
    ARROW_DOWN = "󰁢"
    CHECK = "󰄬"
    CHECK_CIRCLE = "󰄵"
    ERROR = "󰅖"
    ERROR_CIRCLE = "󰅘"
    WARNING = "󰀪"
    INFO = "󰌶"
    BULLET = "󰅂"

    # Actions
    ROCKET = "󱐋"
    GEAR = "󰒓"
    LOCK = "󰌾"
    LOCK_OPEN = "󰌿"
    GLOBE = "󰋉"
    HEART = "󰨞"
    STAR = "󰄉"
    STAR_FILL = "󰓥"
    CLOCK = "󰅐"
    USER = "󰙲"
    USERS = "󰿅"

    # Dev Tools
    TERMINAL = "󰆍"
    SERVER = "󰌈"
    CODE = "󰡄"
    EDITOR = "󰨞"
    DEBUG = "󰃤"
    TEST = "󰙨"
    SHELL = "󱓞"
    URL = "󰌌"
    CACHE = "󰩺"

    # File System
    FOLDER = "󰉋"
    FOLDER_OPEN = "󰉌"
    FILE = "󰡄"
    FILE_CONFIG = "󰒓"
    TRASH = "󰩺"
    SEARCH = "󰍉"

    # Django Specific
    APP = "󰣆"
    MODEL = "󰤤"
    MIGRATION = "󰏘"
    STACK = "󰌘"
    SETTINGS = "󰒓"

    # Status
    STATUS_SUCCESS = "󰄬"
    STATUS_ERROR = "󰅖"
    STATUS_WARNING = "󰀪"
    STATUS_INFO = "󰌶"
    STATUS_RUNNING = "󰝤"
    STATUS_STOPPED = "󰅛"


# =============================================================================
# COLOR THEME - Cyberpunk Neon
# =============================================================================


class Theme:
    """Cyberpunk color palette."""

    PRIMARY = "#00f2fe"  # Neon Cyan
    SECONDARY = "#4facfe"  # Electric Blue
    ACCENT = "#f355da"  # Neon Pink
    SUCCESS = "#00ffcc"  # Mint Green
    WARNING = "#ffb86c"  # Soft Orange
    ERROR = "#ff5555"  # Coral Red
    INFO = "#8be9fd"  # Soft Cyan
    MUTED = "#6272a4"  # Muted Grey
    TEXT = "#f8f8f2"  # Off-white
    BORDER = "#3a3f5e"  # Border
    BG_DARK = "#0a0e27"  # Dark background


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
        time.sleep(0.005)

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
                "--yes",
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
# PROJECT DASHBOARD
# =============================================================================


def show_dashboard() -> bool:
    """Show Django project dashboard."""
    try:
        detector = DjangoProjectDetector()
        if not detector.is_django_project:
            return False

        info = detector.project_info

        table = Table(box=box.ROUNDED, border_style=Theme.BORDER, show_header=False)
        table.add_column("", style=Theme.ACCENT, width=16)
        table.add_column("", style=Theme.PRIMARY)

        table.add_row(f"{NF.FOLDER} Project", str(info.get("project_name", "Unknown")))
        table.add_row(f"{NF.GIT} Branch", str(info.get("git_branch", "N/A")))
        table.add_row(
            f"{NF.TERMINAL} Venv", "Active" if info.get("venv_active") else "Inactive"
        )
        table.add_row(
            f"{NF.SERVER} Server",
            "Running" if info.get("server_running") else "Stopped",
        )
        table.add_row(f"{NF.APP} Apps", str(len(info.get("apps", []))))
        table.add_row(f"{NF.MODEL} Models", str(info.get("models_count", 0)))
        table.add_row(
            f"{NF.MIGRATION} Migrations",
            "Needed" if info.get("needs_migrations") else "Up to date",
        )

        dashboard = Panel(
            table,
            title=f"  {NF.SETTINGS}  Django Project Status  ",
            title_align="center",
            border_style=Theme.PRIMARY,
        )
        console.print(center(dashboard, width=70))
        return True
    except Exception:
        return False


# =============================================================================
# SMART COMMANDS
# =============================================================================


def get_smart_commands() -> List[Dict]:
    """Get smart Django commands."""
    return [
        {"name": "Run Server", "action": "runserver", "icon": NF.SERVER},
        {"name": "Make Migrations", "action": "makemigrations", "icon": NF.MIGRATION},
        {"name": "Migrate", "action": "migrate", "icon": NF.DATABASE},
        {"name": "Create Superuser", "action": "createsuperuser", "icon": NF.USER},
        {"name": "Run Tests", "action": "test", "icon": NF.TEST},
        {"name": "Create New App", "action": "create_app", "icon": NF.APP},
        {"name": "Django Shell", "action": "shell", "icon": NF.SHELL},
        {"name": "Clear Cache", "action": "clear_cache", "icon": NF.CACHE},
    ]


def run_command(action: str, project_path: Path, scaffolder=None, project_name=None):
    """Run Django management command."""
    commands = {
        "runserver": ["uv", "run", "manage.py", "runserver"],
        "makemigrations": ["uv", "run", "manage.py", "makemigrations"],
        "migrate": ["uv", "run", "manage.py", "migrate"],
        "createsuperuser": ["uv", "run", "manage.py", "createsuperuser"],
        "test": ["uv", "run", "manage.py", "test"],
        "shell": ["uv", "run", "manage.py", "shell"],
    }

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

    if action == "clear_cache":
        for pycache in project_path.rglob("__pycache__"):
            shutil.rmtree(pycache)
        show_success("Cache Cleared", "All Python cache files removed")
        return True

    cmd = commands.get(action)
    if not cmd:
        show_error("Unknown Command", f"Command '{action}' not recognized")
        return False

    try:
        subprocess.run(cmd, cwd=project_path)
        return True
    except KeyboardInterrupt:
        show_warning("Command Interrupted", "Operation cancelled")
        return True
    except Exception as e:
        show_error("Command Failed", str(e))
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
# MAIN
# =============================================================================


def main() -> int:
    """Main entry point."""
    try:
        # Check if inside Django project
        if show_dashboard():
            console.print()

            commands = get_smart_commands()
            choices = []
            for cmd in commands:
                choices.append(
                    Choice(
                        value=cmd["action"], name=f"  {cmd['icon']}  {cmd['name']:<18}"
                    )
                )

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
                return 0 if run_command(action, Path.cwd()) else 1

        # New project creation
        console.clear()
        print_banner()

        if not check_prerequisites():
            return 1

        show_features()

        # Project name
        print_rule("Project Setup")
        console.print()

        project_name = inquirer.text(
            message=f"[bold {Theme.PRIMARY}]{NF.ARROW_RIGHT}  Project name:[/]",
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
    except AJOError as e:
        show_error("AJO Error", str(e))
        return 1
    except Exception as e:
        show_error("Unexpected Error", str(e))
        console.print(center(f"[italic {Theme.MUTED}]Please report this on GitHub[/]"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
