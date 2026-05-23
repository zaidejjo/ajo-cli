"""Project detector - detects Django projects and their state."""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple


class DjangoProjectDetector:
    """Detects if current directory is a Django project and extracts info."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path.cwd()
        self.is_django_project = False
        self.project_info: Dict = {
            "project_name": "Unknown",
            "settings_module": "Unknown",
            "apps": [],
            "needs_migrations": False,
            "server_running": False,
            "venv_active": False,
            "git_branch": "N/A",
            "models_count": 0,
            "unapplied_migrations": [],
        }
        self._detect()

    def _detect(self) -> None:
        """Detect Django project and gather information."""
        # Ignore the ajo-cli tool directory
        if self.path.name == "ajo-cli":
            self.is_django_project = False
            return

        # Look for manage.py
        manage_py = self.path / "manage.py"
        if not manage_py.exists():
            # Try to find it in parent directories
            for parent in self.path.parents:
                if (parent / "manage.py").exists():
                    self.path = parent
                    manage_py = parent / "manage.py"
                    break

        if not manage_py.exists():
            self.is_django_project = False
            return

        # Verify it's a real Django project
        try:
            content = manage_py.read_text()
            if "django.core.management" not in content:
                self.is_django_project = False
                return
        except Exception:
            self.is_django_project = False
            return

        self.is_django_project = True

        # Extract project name from manage.py
        try:
            content = manage_py.read_text()
            match = re.search(r"DJANGO_SETTINGS_MODULE\s*=\s*['\"]([^'\"]+)", content)
            if match:
                self.project_info["settings_module"] = match.group(1)
                self.project_info["project_name"] = match.group(1).split(".")[0]
            else:
                self.project_info["project_name"] = self.path.name
        except Exception:
            self.project_info["project_name"] = self.path.name

        # Detect apps
        self.project_info["apps"] = self._detect_apps()

        # Detect if migrations are needed
        self.project_info["needs_migrations"] = self._check_migrations_needed()

        # Detect if server is running
        self.project_info["server_running"] = self._check_server_running()

        # Detect virtual environment
        self.project_info["venv_active"] = self._check_venv()

        # Get git info
        self.project_info["git_branch"] = self._get_git_branch()

        # Count models
        self.project_info["models_count"] = self._count_models()

        # Check for unapplied migrations
        self.project_info["unapplied_migrations"] = self._check_unapplied_migrations()

    def _detect_apps(self) -> List[Dict]:
        """Detect all Django apps in the project."""
        apps = []

        try:
            for item in self.path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    if (item / "apps.py").exists() or (item / "models.py").exists():
                        is_installed = self._is_in_installed_apps(item.name)
                        apps.append(
                            {
                                "name": item.name,
                                "path": str(item),
                                "has_models": (item / "models.py").exists(),
                                "has_admin": (item / "admin.py").exists(),
                                "has_views": (item / "views.py").exists(),
                                "has_urls": (item / "urls.py").exists(),
                                "is_installed": is_installed,
                            }
                        )
        except Exception:
            pass

        return apps

    def _is_in_installed_apps(self, app_name: str) -> bool:
        """Check if app is in INSTALLED_APPS."""
        try:
            settings_path = self.path / self.project_info.get("project_name", "") / "settings.py"
            if not settings_path.exists():
                settings_path = self.path / "settings.py"

            if settings_path.exists():
                content = settings_path.read_text()
                return f"'{app_name}'" in content or f'"{app_name}"' in content
        except Exception:
            pass
        return False

    def _check_migrations_needed(self) -> bool:
        """Check if there are model changes without migrations."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "manage.py", "makemigrations", "--dry-run"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "No changes detected" not in result.stdout and result.returncode == 0
        except Exception:
            return False

    def _check_server_running(self) -> bool:
        """Check if Django development server is running."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", 8000))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _check_venv(self) -> bool:
        """Check if virtual environment is active."""
        return bool(os.environ.get("VIRTUAL_ENV")) or bool(os.environ.get("UV_PROJECT_ENVIRONMENT"))

    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return "N/A"

    def _count_models(self) -> int:
        """Count total models in all apps."""
        count = 0
        try:
            for app in self.project_info.get("apps", []):
                models_file = Path(app["path"]) / "models.py"
                if models_file.exists():
                    content = models_file.read_text()
                    matches = re.findall(r"class\s+(\w+)\(.*models\.Model", content)
                    count += len(matches)
        except Exception:
            pass
        return count

    def _check_unapplied_migrations(self) -> List[str]:
        """Check for unapplied migrations."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "manage.py", "showmigrations", "--plan"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                unapplied = []
                for line in result.stdout.split("\n"):
                    if "[ ]" in line and not line.strip().startswith("["):
                        unapplied.append(line.strip())
                return unapplied
        except Exception:
            pass
        return []

    def get_status_dashboard(self) -> str:
        """Generate a status dashboard."""
        if not self.is_django_project:
            return "Not a Django project"

        # Safe string formatting with fallbacks
        project_name = self.project_info.get("project_name", "Unknown")[:44]
        git_branch = self.project_info.get("git_branch", "N/A")[:47]
        venv_status = "✅ Active" if self.project_info.get("venv_active") else "❌ Inactive"
        server_status = "🟢 Running" if self.project_info.get("server_running") else "⚫ Stopped"
        apps_count = str(self.project_info.get("apps", []))[:48]
        models_count = str(self.project_info.get("models_count", 0))[:48]
        needs_migrations = (
            "⚠️ Needed" if self.project_info.get("needs_migrations") else "✅ Up to date"
        )
        unapplied_count = str(len(self.project_info.get("unapplied_migrations", [])))[:44]

        status = f"""
╭─────────────────── Django Project Status ───────────────────╮
│                                                             │
│  📁 Project: {project_name:<44} │
│  🌿 Branch: {git_branch:<47} │
│  🐍 Venv: {venv_status:<44} │
│  🖥️  Server: {server_status:<45} │
│                                                             │
│  📦 Apps: {apps_count:<48} │
│  🗄️  Models: {models_count:<48} │
│                                                             │
│  📝 Migrations: {needs_migrations:<40} │
│  ⏳ Unapplied: {unapplied_count:<44} │
│                                                             │
╰─────────────────────────────────────────────────────────────╯
"""
        return status


class SmartDjangoCLI:
    """Smart CLI for Django project management."""

    def __init__(self, detector: DjangoProjectDetector):
        self.detector = detector

    def get_commands(self) -> List[Dict]:
        """Get available commands based on project state."""
        commands = [
            {
                "name": "🏃 Run Server",
                "action": "runserver",
                "description": "Start development server",
            },
            {
                "name": "🔄 Make Migrations",
                "action": "makemigrations",
                "description": "Create new migrations",
            },
            {"name": "⚙️ Migrate", "action": "migrate", "description": "Apply migrations"},
            {
                "name": "👤 Create Superuser",
                "action": "createsuperuser",
                "description": "Create admin user",
            },
            {"name": "🧪 Run Tests", "action": "test", "description": "Run all tests"},
            {
                "name": "📱 Create New App",
                "action": "create_app",
                "description": "Scaffold a new app",
            },
            {"name": "🔧 Django Shell", "action": "shell", "description": "Open Django shell"},
            {"name": "📊 Show URLs", "action": "show_urls", "description": "List all URL patterns"},
            {"name": "🧹 Clear Cache", "action": "clear_cache", "description": "Clear all caches"},
            {
                "name": "📝 Check Deployment",
                "action": "check",
                "description": "Check deployment readiness",
            },
            {
                "name": "🗑️ Manage Apps",
                "action": "manage_apps",
                "description": "Add/remove installed apps",
            },
        ]

        # Highlight needed actions
        if self.detector.project_info.get("needs_migrations"):
            commands.insert(
                1,
                {
                    "name": "⚠️ Make Migrations (Needed!)",
                    "action": "makemigrations",
                    "description": "Model changes detected!",
                },
            )

        unapplied = len(self.detector.project_info.get("unapplied_migrations", []))
        if unapplied > 0:
            commands.insert(
                2,
                {
                    "name": f"⚠️ Migrate ({unapplied} pending)",
                    "action": "migrate",
                    "description": "Apply pending migrations",
                },
            )

        return commands
