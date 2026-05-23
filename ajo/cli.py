"""Professional TUI CLI for Django scaffolding with GitHub and Database support."""

import sys
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box
from rich.align import Align
from rich.columns import Columns

from ajo.templates.django_app import DjangoProjectScaffolder
from ajo.validators import ProjectNameValidator
from ajo.utils import check_uv_installed, get_uv_version
from ajo.exceptions import AJOError
from ajo.detector import DjangoProjectDetector
from ajo.github_integration import GitHubManager
from ajo.database_manager import DatabaseManager

console = Console()


def print_professional_banner():
    """Display stunning professional TUI banner."""
    banner_art = Text(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║    █████╗  ██╗  ██████╗      ██████╗ ██╗     ██╗                           ║
║   ██╔══██╗██║ ██╔═══██╗     ██╔═══██╗██║     ██║                           ║
║   ███████║██║ ██║   ██║     ██║   ██║██║     ██║                           ║
║   ██╔══██║██║ ██║   ██║     ██║   ██║██║     ██║                           ║
║   ██║  ██║██║ ╚██████╔╝     ╚██████╔╝███████╗██║                           ║
║   ╚═╝  ╚═╝╚═╝  ╚═════╝       ╚═════╝ ╚══════╝╚═╝                           ║
║                                                                              ║
║                    ┌─────────────────────────────────────────┐              ║
║                    │  The Ultimate Django Scaffolding Suite  │              ║
║                    │         Professional TUI Edition       │              ║
║                    └─────────────────────────────────────────┘              ║
║                                                                              ║
║                         ⚡ Powered by UV & Ruff ⚡                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""",
        style="bold magenta",
    )

    console.print(Align.center(banner_art))
    console.print()


def show_feature_grid():
    """Display feature grid in TUI style."""
    features = [
        Panel(
            "[cyan]📦[/cyan] [green]SQLite/PostgreSQL/MySQL[/green]", width=30, border_style="dim"
        ),
        Panel("[cyan]🐙[/cyan] [green]GitHub Integration[/green]", width=30, border_style="dim"),
        Panel("[cyan]🚀[/cyan] [green]CI/CD with Ruff[/green]", width=30, border_style="dim"),
        Panel("[cyan]🎨[/cyan] [green]Bootstrap 5 Themes[/green]", width=30, border_style="dim"),
        Panel("[cyan]🔒[/cyan] [green]Auto .env Security[/green]", width=30, border_style="dim"),
        Panel("[cyan]📱[/cyan] [green]Smart App Scaffolding[/green]", width=30, border_style="dim"),
    ]
    console.print(Columns(features, equal=True, expand=False))
    console.print()


def check_prerequisites() -> bool:
    """Check if required tools are installed."""
    uv_ok = check_uv_installed()
    if not uv_ok:
        console.print("[red]❌ uv is not installed![/red]")
        console.print("[yellow]Please install uv first:[/yellow]")
        console.print("  [cyan]curl -LsSf https://astral.sh/uv/install.sh | sh[/cyan]")
        return False

    uv_version = get_uv_version()
    console.print(f"[green]✓[/green] uv detected: {uv_version}")

    # Check gh (optional, just warn)
    gh_check = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    if gh_check.returncode == 0:
        console.print(f"[green]✓[/green] GitHub CLI detected")
    else:
        console.print(
            "[yellow]⚠️ GitHub CLI not installed (optional for GitHub integration)[/yellow]"
        )

    return True


def select_database() -> Tuple[str, Dict]:
    """Interactive database selection with TUI."""
    console.print("\n[bold cyan]🗄️  Database Configuration[/bold cyan]\n")

    db_choices = [
        Choice(value="sqlite", name="📁 SQLite - Lightweight, file-based (default)"),
        Choice(value="postgresql", name="🐘 PostgreSQL - Production-ready, feature-rich"),
        Choice(value="mysql", name="🦬 MySQL - Popular, reliable"),
    ]

    db_choice = inquirer.select(
        message="Select your database:",
        choices=db_choices,
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
        # Ask for credentials
        console.print("\n[yellow]Enter database credentials (press Enter for defaults):[/yellow]")

        db_name = inquirer.text(message="Database name:", default=selected_config["name"]).execute()
        db_user = inquirer.text(message="Username:", default=selected_config["user"]).execute()
        db_password = inquirer.secret(message="Password:").execute()
        db_host = inquirer.text(message="Host:", default=selected_config["host"]).execute()
        db_port = inquirer.text(message="Port:", default=selected_config["port"]).execute()

        selected_config["name"] = db_name
        selected_config["user"] = db_user
        selected_config["password"] = db_password or ""
        selected_config["host"] = db_host
        selected_config["port"] = db_port

    return db_choice, selected_config


def setup_github_integration(project_path: Path, project_name: str) -> bool:
    """Setup GitHub repository and push initial commit."""
    console.print("\n[bold cyan]🐙 GitHub Integration[/bold cyan]\n")

    use_github = inquirer.confirm(
        message="Do you want to create a GitHub repository?",
        default=False,
    ).execute()

    if not use_github:
        return False

    # Check gh CLI
    gh_check = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    if gh_check.returncode != 0:
        console.print("[red]❌ GitHub CLI not installed![/red]")
        console.print("[yellow]Install it from: https://cli.github.com/[/yellow]")
        return False

    # Check login status
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if auth_check.returncode != 0:
        console.print("[red]❌ Not logged into GitHub![/red]")
        console.print("[yellow]Run: [cyan]gh auth login[/cyan][/yellow]")
        return False

    # Repository visibility
    visibility = inquirer.select(
        message="Repository visibility:",
        choices=[
            Choice(value="public", name="🌍 Public - Anyone can see"),
            Choice(value="private", name="🔒 Private - Only you and collaborators"),
        ],
    ).execute()

    # Create repo
    console.print("[yellow]Creating GitHub repository...[/yellow]")

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit from AJO CLI"],
        cwd=project_path,
        capture_output=True,
    )

    # Create repo and push
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
        console.print(f"[green]✓ GitHub repository '{project_name}' created and pushed![/green]")
        return True
    else:
        console.print(f"[red]❌ Failed to create repository: {result.stderr}[/red]")
        return False


def setup_ci_cd(project_path: Path) -> bool:
    """Setup GitHub Actions CI/CD with Ruff."""
    console.print("\n[bold cyan]🔄 CI/CD Pipeline Setup[/bold cyan]")

    use_cicd = inquirer.confirm(
        message="Do you want to setup CI/CD with GitHub Actions?",
        default=True,
    ).execute()

    if not use_cicd:
        return False

    # Create .github/workflows directory
    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # Create CI workflow with Ruff
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
      run: uv run ruff format --check .
  
  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    
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

    # Create ruff configuration
    pyproject_toml_path = project_path / "pyproject.toml"
    if pyproject_toml_path.exists():
        current = pyproject_toml_path.read_text()
        ruff_config = """
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "single"
indent-style = "space"
"""
        pyproject_toml_path.write_text(current + ruff_config)

    console.print("[green]✓ CI/CD pipeline configured with Ruff![/green]")
    return True


def show_project_dashboard():
    """Show beautiful dashboard for existing Django project."""
    detector = DjangoProjectDetector()

    if not detector.is_django_project:
        return False

    # Create fancy dashboard
    dashboard = Panel(
        Text.from_markup(f"""
[bold cyan]📁 Project:[/bold cyan] {detector.project_info.get("project_name", "Unknown")}
[bold cyan]🌿 Branch:[/bold cyan] {detector.project_info.get("git_branch", "N/A")}
[bold cyan]🐍 Venv:[/bold cyan] {"✅ Active" if detector.project_info.get("venv_active") else "❌ Inactive"}
[bold cyan]🖥️  Server:[/bold cyan] {"🟢 Running" if detector.project_info.get("server_running") else "⚫ Stopped"}

[bold cyan]📦 Apps:[/bold cyan] {len(detector.project_info.get("apps", []))}
[bold cyan]🗄️  Models:[/bold cyan] {detector.project_info.get("models_count", 0)}

[bold cyan]📝 Migrations:[/bold cyan] {"⚠️ Needed" if detector.project_info.get("needs_migrations") else "✅ Up to date"}
[bold cyan]⏳ Unapplied:[/bold cyan] {len(detector.project_info.get("unapplied_migrations", []))}
        """),
        title="[bold magenta]🔍 Django Project Status[/bold magenta]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(dashboard)

    return True


def get_smart_commands() -> List[Dict]:
    """Get list of smart Django commands."""
    return [
        {
            "name": "🏃 Run Server",
            "action": "runserver",
            "description": "Start development server",
            "icon": "🚀",
        },
        {
            "name": "🔄 Make Migrations",
            "action": "makemigrations",
            "description": "Create new migrations",
            "icon": "📝",
        },
        {"name": "⚙️ Migrate", "action": "migrate", "description": "Apply migrations", "icon": "🔄"},
        {
            "name": "👤 Create Superuser",
            "action": "createsuperuser",
            "description": "Create admin user",
            "icon": "👑",
        },
        {"name": "🧪 Run Tests", "action": "test", "description": "Run all tests", "icon": "✅"},
        {
            "name": "📱 Create New App",
            "action": "create_app",
            "description": "Scaffold a new app",
            "icon": "📦",
        },
        {
            "name": "🔧 Django Shell",
            "action": "shell",
            "description": "Open Django shell",
            "icon": "💻",
        },
        {
            "name": "📊 Show URLs",
            "action": "show_urls",
            "description": "List all URL patterns",
            "icon": "🔗",
        },
        {
            "name": "🧹 Clear Cache",
            "action": "clear_cache",
            "description": "Clear all caches",
            "icon": "🗑️",
        },
        {
            "name": "📝 Check Deployment",
            "action": "check",
            "description": "Check deployment readiness",
            "icon": "🔍",
        },
    ]


def run_django_command(action: str, project_path: Path):
    """Execute Django management command."""
    commands_map = {
        "runserver": ["uv", "run", "python", "manage.py", "runserver"],
        "makemigrations": ["uv", "run", "python", "manage.py", "makemigrations"],
        "migrate": ["uv", "run", "python", "manage.py", "migrate"],
        "createsuperuser": ["uv", "run", "python", "manage.py", "createsuperuser"],
        "test": ["uv", "run", "python", "manage.py", "test"],
        "shell": ["uv", "run", "python", "manage.py", "shell"],
        "check": ["uv", "run", "python", "manage.py", "check", "--deploy"],
    }

    if action == "clear_cache":
        for pycache in project_path.rglob("__pycache__"):
            shutil.rmtree(pycache)
        console.print("[green]✓ Cache cleared![/green]")
        return True

    if action == "show_urls":
        cmd = ["uv", "run", "python", "manage.py", "show_urls"]
    else:
        cmd = commands_map.get(action)

    if not cmd:
        console.print(f"[red]Unknown command: {action}[/red]")
        return False

    console.print(f"[yellow]🚀 Running: {' '.join(cmd)}[/yellow]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        subprocess.run(cmd, cwd=project_path)
        return True
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Command interrupted[/yellow]")
        return True
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return False


def main() -> int:
    """Main entry point for CLI."""
    try:
        # Check if we're inside a Django project
        if show_project_dashboard():
            console.print("\n[bold cyan]🛠️ Smart Django Commands[/bold cyan]\n")

            commands = get_smart_commands()
            choices = []
            for cmd in commands:
                choices.append(
                    Choice(
                        value=cmd["action"],
                        name=f"{cmd['icon']} {cmd['name']} - {cmd['description']}",
                    )
                )

            choices.append(Separator())
            choices.append(
                Choice(value="new_project", name="✨ Create New Project (Different Directory)")
            )
            choices.append(Choice(value="exit", name="🚪 Exit"))

            action = inquirer.select(
                message="What would you like to do?",
                choices=choices,
            ).execute()

            if action == "exit":
                return 0
            elif action == "new_project":
                pass  # Continue to new project creation
            else:
                run_django_command(action, Path.cwd())
                return 0

        # New project creation - Professional TUI
        console.clear()
        print_professional_banner()

        if not check_prerequisites():
            return 1

        show_feature_grid()

        console.print("\n[bold yellow]📋 Project Configuration[/bold yellow]\n")

        # Project name input with validation
        project_name = None
        while True:
            raw_name = inquirer.text(
                message="Project name:",
                validate=lambda x: len(x.strip()) > 0,
                instruction="(letters, numbers, underscores)",
            ).execute()

            is_valid, error = ProjectNameValidator.validate(raw_name)
            if is_valid:
                project_name = raw_name
                break

            console.print(f"[red]❌ {error}[/red]")

            sanitized = ProjectNameValidator.sanitize(raw_name)
            if sanitized != raw_name:
                use_suggestion = inquirer.confirm(
                    message=f"Did you mean [cyan]{sanitized}[/cyan]?",
                    default=True,
                ).execute()
                if use_suggestion:
                    project_name = sanitized
                    console.print(f"[green]✓ Using: {project_name}[/green]")
                    break

        if not project_name:
            project_name = "myproject"
            console.print(f"[yellow]Using default name: {project_name}[/yellow]")

        # Architecture preset selection
        console.print("\n[bold cyan]🏗️  Architecture Preset[/bold cyan]\n")
        preset_table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        preset_table.add_column("Preset", style="bold green")
        preset_table.add_column("Description", style="white")
        preset_table.add_column("Includes", style="dim")
        preset_table.add_row("📦 Standard Monolith", "Traditional Django", "HTML + Bootstrap 5")
        preset_table.add_row("🚀 REST API Ready", "DRF + CORS", "API + JWT Ready")
        console.print(preset_table)

        preset = inquirer.select(
            message="Choose architecture preset:",
            choices=[
                Choice(
                    value="Standard Monolith",
                    name="📦 Standard Monolith - Traditional Django with Bootstrap",
                ),
                Choice(
                    value="REST API Ready", name="🚀 REST API Ready - DRF + CORS pre-configured"
                ),
            ],
        ).execute()

        # Database selection
        db_type, db_config = select_database()

        # Create project with database config
        scaffolder = DjangoProjectScaffolder(project_name, preset, db_type, db_config)
        if not scaffolder.scaffold():
            return 1

        # Create apps loop
        while True:
            console.print("\n[bold cyan]📱 App Management[/bold cyan]")
            add_app = inquirer.confirm(
                message="Create a new Django app?",
                default=False,
            ).execute()

            if not add_app:
                break

            while True:
                app_name = inquirer.text(
                    message="App name:",
                    validate=lambda x: len(x.strip()) > 0,
                    instruction="(lowercase, letters only)",
                ).execute()

                if not app_name or not app_name[0].isalpha():
                    console.print("[red]❌ App name must start with a letter[/red]")
                    continue
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", app_name):
                    console.print(
                        "[red]❌ App name can only contain letters, numbers, and underscores[/red]"
                    )
                    continue
                break

            if not scaffolder.create_app(app_name):
                console.print("[yellow]⚠️ Continuing with project setup...[/yellow]")

        # GitHub Integration
        github_created = setup_github_integration(Path.cwd() / project_name, project_name)

        # CI/CD Setup
        setup_ci_cd(Path.cwd() / project_name)

        # Final success message
        console.print("\n")

        success_panel = Panel(
            Text.from_markup(f"""
[bold green]✨ AJO Setup Complete! ✨[/bold green]

[white]Your project [bold magenta]{project_name}[/bold magenta] is ready![/white]

[yellow]📦 Database:[/yellow] {db_type.upper()}
[yellow]🐙 GitHub:[/yellow] {"✅ Created" if github_created else "❌ Skipped"}
[yellow]🔄 CI/CD:[/yellow] {"✅ Configured with Ruff" if Path(Path.cwd() / project_name / ".github").exists() else "❌ Skipped"}

[bold green]Next steps:[/bold green]
  [cyan]cd {project_name}[/cyan]
  [cyan]uv run python manage.py migrate[/cyan]
  [cyan]uv run python manage.py createsuperuser[/cyan] (optional)
  [cyan]uv run python manage.py runserver[/cyan]

[dim]➜ Visit http://127.0.0.1:8000[/dim]
            """),
            title="🎉 Success",
            border_style="magenta",
            padding=(1, 2),
        )
        console.print(success_panel)

        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user[/yellow]")
        return 130
    except AJOError as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {e}[/red]")
        console.print("[dim]Please report this issue on GitHub[/dim]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
