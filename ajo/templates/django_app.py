"""Core engine for Django project scaffolding with full database and production support."""

import subprocess
import sys
import re
import shutil
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

from ajo.utils import generate_secure_key, rollback_project, append_to_installed_apps
from ajo.core.exceptions import CommandExecutionError

console = Console()


class DjangoProjectScaffolder:
    """
    Professional Django project scaffolder.

    Supports:
    - Multiple databases (SQLite, PostgreSQL, MySQL)
    - Architecture presets (Monolith, REST API)
    - Automatic app creation
    - Environment configuration
    - Bootstrap 5 templates
    """

    def __init__(
        self,
        project_name: str,
        preset: str = "Standard Monolith",
        db_type: str = "sqlite",
        db_config: Dict[str, Any] = None,
    ):
        """
        Initialize the scaffolder.

        Args:
            project_name: Name of the Django project
            preset: Architecture preset (Standard Monolith or REST API Ready)
            db_type: Database type (sqlite, postgresql, mysql)
            db_config: Database configuration (credentials, host, port, etc.)
        """
        self.project_name = project_name
        self.preset = preset
        self.db_type = db_type
        self.db_config = db_config or {}
        self.root_path = Path.cwd() / project_name
        self.settings_path: Optional[Path] = None
        self.project_package_path: Optional[Path] = None

    def _run_command(
        self, command: list[str], description: str, cwd: Optional[Path] = None
    ) -> str:
        """Run a subprocess command with professional progress spinner."""
        cwd_path = cwd or self.root_path

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold yellow]{task.description}"),
            BarColumn(bar_width=40),
            TimeElapsedColumn(),
            transient=False,
        ) as progress:
            task = progress.add_task(f"[cyan]⏳ {description}", total=None)

            try:
                result = subprocess.run(
                    command,
                    cwd=cwd_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                progress.update(task, completed=100)
                progress.remove_task(task)

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or result.stdout.strip()
                    raise CommandExecutionError(
                        f"Command failed: {' '.join(command)}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"Error: {error_msg[:500]}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    )
                return result.stdout
            except subprocess.SubprocessError as e:
                progress.remove_task(task)
                raise CommandExecutionError(f"Failed to execute command: {str(e)}")

    def _install_base_dependencies(self):
        """Install base Django dependencies."""
        deps = ["django", "python-dotenv"]

        if self.preset == "REST API Ready":
            deps.extend(
                ["djangorestframework", "django-cors-headers", "drf-spectacular"]
            )

        console.print(f"[bold cyan]📦 Installing {len(deps)} packages...[/bold cyan]")
        self._run_command(["uv", "add"] + deps, f"Installing {', '.join(deps)}")
        console.print(
            f"[bold green]✓[/bold green] Packages installed: {', '.join(deps)}"
        )

    def _install_database_packages(self):
        """Install database-specific packages."""
        if self.db_type == "postgresql":
            console.print("[cyan]🐘 Installing PostgreSQL driver...[/cyan]")
            self._run_command(
                ["uv", "add", "psycopg2-binary"], "Installing psycopg2-binary"
            )
            console.print("[bold green]✓[/bold green] PostgreSQL driver installed")
        elif self.db_type == "mysql":
            console.print("[cyan]🦬 Installing MySQL driver...[/cyan]")
            self._run_command(["uv", "add", "mysqlclient"], "Installing mysqlclient")
            console.print("[bold green]✓[/bold green] MySQL driver installed")
        elif self.db_type == "sqlite":
            console.print("[dim]📁 Using SQLite (no additional driver needed)[/dim]")

    def _get_database_settings(self) -> str:
        """Generate database configuration string for settings.py."""
        if self.db_type == "sqlite":
            return """
# ============================================================
# DATABASE CONFIGURATION
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
"""
        elif self.db_type == "postgresql":
            name = self.db_config.get("name", "postgres")
            user = self.db_config.get("user", "postgres")
            password = self.db_config.get("password", "")
            host = self.db_config.get("host", "localhost")
            port = self.db_config.get("port", "5432")

            return f"""
# ============================================================
# DATABASE CONFIGURATION - PostgreSQL
# ============================================================
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', '{name}'),
        'USER': os.getenv('DB_USER', '{user}'),
        'PASSWORD': os.getenv('DB_PASSWORD', '{password}'),
        'HOST': os.getenv('DB_HOST', '{host}'),
        'PORT': os.getenv('DB_PORT', '{port}'),
    }}
}}
"""
        elif self.db_type == "mysql":
            name = self.db_config.get("name", "mysql")
            user = self.db_config.get("user", "root")
            password = self.db_config.get("password", "")
            host = self.db_config.get("host", "localhost")
            port = self.db_config.get("port", "3306")

            return f"""
# ============================================================
# DATABASE CONFIGURATION - MySQL
# ============================================================
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', '{name}'),
        'USER': os.getenv('DB_USER', '{user}'),
        'PASSWORD': os.getenv('DB_PASSWORD', '{password}'),
        'HOST': os.getenv('DB_HOST', '{host}'),
        'PORT': os.getenv('DB_PORT', '{port}'),
        'OPTIONS': {{
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        }},
    }}
}}
"""
        return ""

    def _get_env_variables(self) -> str:
        """Generate .env file content based on database type."""
        secret_key = generate_secure_key()

        env_content = f"""# ============================================================
# DJANGO SECURITY
# ============================================================
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
DB_TYPE={self.db_type}
"""

        if self.db_type == "postgresql":
            env_content += f"""DB_NAME={self.db_config.get("name", "postgres")}
DB_USER={self.db_config.get("user", "postgres")}
DB_PASSWORD={self.db_config.get("password", "")}
DB_HOST={self.db_config.get("host", "localhost")}
DB_PORT={self.db_config.get("port", "5432")}
"""
        elif self.db_type == "mysql":
            env_content += f"""DB_NAME={self.db_config.get("name", "mysql")}
DB_USER={self.db_config.get("user", "root")}
DB_PASSWORD={self.db_config.get("password", "")}
DB_HOST={self.db_config.get("host", "localhost")}
DB_PORT={self.db_config.get("port", "3306")}
"""

        return env_content

    def _create_manual_django_project(self):
        """Create Django project structure manually if startproject fails."""
        console.print("[yellow]📁 Creating Django project manually...[/yellow]")

        # Create manage.py
        manage_py = f'''#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.project_name}.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed."
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
'''
        (self.root_path / "manage.py").write_text(manage_py)

        # Create project package
        project_pkg = self.root_path / self.project_name
        project_pkg.mkdir(exist_ok=True)

        # Create __init__.py
        (project_pkg / "__init__.py").write_text("")

        # Create asgi.py
        asgi_py = f'''"""
ASGI config for {self.project_name} project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.project_name}.settings')
application = get_asgi_application()
'''
        (project_pkg / "asgi.py").write_text(asgi_py)

        # Create wsgi.py
        wsgi_py = f'''"""
WSGI config for {self.project_name} project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.project_name}.settings')
application = get_wsgi_application()
'''
        (project_pkg / "wsgi.py").write_text(wsgi_py)

        # Create urls.py
        urls_py = f'''"""
URL configuration for {self.project_name} project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
]
'''
        (project_pkg / "urls.py").write_text(urls_py)

        # Create settings.py
        settings_py = f'''"""
Django settings for {self.project_name} project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{self.project_name}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = '{self.project_name}.wsgi.application'

{self._get_database_settings()}

AUTH_PASSWORD_VALIDATORS = [
    {{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',}},
    {{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',}},
    {{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',}},
    {{'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',}},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
'''
        (project_pkg / "settings.py").write_text(settings_py)

        self.settings_path = project_pkg / "settings.py"
        self.project_package_path = project_pkg

        console.print("[bold green]✓[/bold green] Django project created manually")

    def _setup_environment(self):
        """Create .env and .gitignore files."""
        env_content = self._get_env_variables()
        (self.root_path / ".env").write_text(env_content)
        console.print("[bold green]✓[/bold green] Environment file created")

        gitignore_content = """# Environment
.env
.venv
venv/
env/

# Python
__pycache__/
*.py[cod]
*.so
.Python
*.egg-info/
dist/
build/

# Database
db.sqlite3
*.sqlite3

# Django
*.log
local_settings.py
/static/
/media/
staticfiles/

# uv
uv.lock

# IDE
.vscode/
.idea/
*.swp
.DS_Store
"""
        (self.root_path / ".gitignore").write_text(gitignore_content)
        console.print("[bold green]✓[/bold green] Git ignore file created")

    def _setup_global_templates(self):
        """Create global templates folder with Bootstrap 5 base.html."""
        templates_dir = self.root_path / "templates"
        templates_dir.mkdir(exist_ok=True)

        base_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AJO Django{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .main-card {
            background: white;
            border-radius: 20px;
            padding: 2rem;
            margin: 2rem 0;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">⚡ AJO Django</a>
        </div>
    </nav>
    <div class="container">
        <div class="main-card">
            {% block content %}
            <div class="text-center">
                <h1>Welcome to Your Django Project</h1>
                <p>Powered by AJO CLI</p>
                <a href="/admin" class="btn btn-primary">Admin Panel</a>
            </div>
            {% endblock %}
        </div>
    </div>
</body>
</html>
"""
        (templates_dir / "base.html").write_text(base_html)
        console.print("[bold green]✓[/bold green] Bootstrap templates created")

    def scaffold(self) -> bool:
        """Create the complete Django project."""
        try:
            if self.root_path.exists():
                console.print(
                    f"[bold red]❌ Directory '{self.project_name}' already exists![/bold red]"
                )
                return False

            console.print(
                f"\n[bold cyan]🚀 Creating project: {self.project_name}[/bold cyan]\n"
            )

            # Step 1: Create directory
            console.print("[yellow]📁 Creating project directory...[/yellow]")
            self.root_path.mkdir(parents=True)
            console.print("[bold green]✓[/bold green] Directory created")

            # Step 2: Initialize uv
            self._run_command(["uv", "init", "--bare"], "Initializing uv project...")
            console.print("[bold green]✓[/bold green] uv project initialized")

            # Step 3: Install base dependencies
            self._install_base_dependencies()

            # Step 4: Install database packages
            self._install_database_packages()

            # Step 5: Create Django project
            console.print("[yellow]📁 Creating Django project structure...[/yellow]")

            original_cwd = Path.cwd()
            parent_dir = self.root_path.parent

            try:
                os.chdir(parent_dir)
                result = subprocess.run(
                    ["uv", "run", "django-admin", "startproject", self.project_name],
                    capture_output=True,
                    text=True,
                )
                os.chdir(original_cwd)

                if result.returncode != 0:
                    self._create_manual_django_project()
                else:
                    console.print("[bold green]✓[/bold green] Django project created")

            except Exception:
                os.chdir(original_cwd)
                self._create_manual_django_project()

            # Locate settings.py
            self.project_package_path = self.root_path / self.project_name
            if not self.project_package_path.exists():
                possible_paths = list(self.root_path.glob("*/settings.py"))
                if possible_paths:
                    self.project_package_path = possible_paths[0].parent
                    self.settings_path = possible_paths[0]
            else:
                self.settings_path = self.project_package_path / "settings.py"

            # Step 6: Setup environment
            self._setup_environment()

            # Step 7: Setup templates
            self._setup_global_templates()

            console.print(
                f"\n[bold green]🎉 Project '{self.project_name}' created successfully![/bold green]"
            )
            return True

        except CommandExecutionError as e:
            console.print(f"\n[bold red]❌ Command Error: {str(e)}[/bold red]")
            console.print("[yellow]🔄 Rolling back changes...[/yellow]")
            rollback_project(self.root_path)
            return False
        except Exception as e:
            console.print(f"\n[bold red]❌ Unexpected Error: {str(e)}[/bold red]")
            console.print("[yellow]🔄 Rolling back changes...[/yellow]")
            rollback_project(self.root_path)
            return False

    def create_app(self, app_name: str) -> bool:
        """Create a new Django app."""
        try:
            console.print(f"\n[cyan]📱 Creating app: {app_name}...[/cyan]")

            result = subprocess.run(
                ["uv", "run", "django-admin", "startapp", app_name],
                cwd=self.root_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                console.print(f"[red]Error: {result.stderr}[/red]")
                return False

            # Create templates directory
            app_template_dir = self.root_path / app_name / "templates" / app_name
            app_template_dir.mkdir(parents=True, exist_ok=True)

            # Create index.html
            index_html = f'{{% extends "base.html" %}}\n\n{{% block title %}}{app_name.title()}{{% endblock %}}\n\n{{% block content %}}\n<div class="container">\n    <h1>{app_name.title()} App</h1>\n    <p>Welcome to the {app_name} application.</p>\n</div>\n{{% endblock %}}\n'
            (app_template_dir / "index.html").write_text(index_html)

            # Create urls.py
            urls_content = f'from django.urls import path\nfrom . import views\n\napp_name = "{app_name}"\n\nurlpatterns = [\n    path("", views.index, name="index"),\n]\n'
            (self.root_path / app_name / "urls.py").write_text(urls_content)

            # Update views.py
            views_content = f'from django.shortcuts import render\n\ndef index(request):\n    return render(request, "{app_name}/index.html")\n'
            (self.root_path / app_name / "views.py").write_text(views_content)

            # Add to INSTALLED_APPS
            if self.settings_path and self.settings_path.exists():
                append_to_installed_apps(self.settings_path, app_name)

            console.print(f"[bold green]✓[/bold green] App '{app_name}' created")
            return True

        except Exception as e:
            console.print(f"[bold red]❌ Failed: {str(e)}[/bold red]")
            return False
