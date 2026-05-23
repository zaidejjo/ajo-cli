"""Professional project detector for Django projects with enhanced state detection."""

import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple


class DjangoProjectDetector:
    """
    Professional Django project detector.

    Detects Django projects, extracts information, and provides
    comprehensive project state analysis.
    """

    def __init__(self, path: Optional[Path] = None):
        """
        Initialize the detector.

        Args:
            path: Path to check (defaults to current working directory)
        """
        self.path = path or Path.cwd()
        self.is_django_project = False
        self.project_info: Dict[str, Any] = {
            "project_name": "Unknown",
            "settings_module": "Unknown",
            "apps": [],
            "needs_migrations": False,
            "server_running": False,
            "venv_active": False,
            "git_branch": "N/A",
            "models_count": 0,
            "unapplied_migrations": [],
            "has_admin": False,
            "has_static": False,
            "has_media": False,
        }
        self._detect()

    def _detect(self) -> None:
        """Detect Django project and gather comprehensive information."""
        # Ignore the ajo-cli tool directory
        if self.path.name == "ajo-cli":
            self.is_django_project = False
            return

        # Look for manage.py
        manage_py = self._find_manage_py()

        if not manage_py:
            self.is_django_project = False
            return

        # Verify it's a real Django project
        if not self._verify_django_project(manage_py):
            self.is_django_project = False
            return

        self.is_django_project = True

        # Extract all project information
        self._extract_project_name(manage_py)
        self.project_info["apps"] = self._detect_apps()
        self.project_info["needs_migrations"] = self._check_migrations_needed()
        self.project_info["server_running"] = self._check_server_running()
        self.project_info["venv_active"] = self._check_venv()
        self.project_info["git_branch"] = self._get_git_branch()
        self.project_info["models_count"] = self._count_models()
        self.project_info["unapplied_migrations"] = self._check_unapplied_migrations()
        self.project_info["has_admin"] = self._check_admin_enabled()
        self.project_info["has_static"] = self._check_static_files()
        self.project_info["has_media"] = self._check_media_files()

    def _find_manage_py(self) -> Optional[Path]:
        """Find manage.py in current or parent directories."""
        manage_py = self.path / "manage.py"
        if manage_py.exists():
            return manage_py

        # Try to find it in parent directories
        for parent in self.path.parents:
            if (parent / "manage.py").exists():
                self.path = parent
                return parent / "manage.py"

        return None

    def _verify_django_project(self, manage_py: Path) -> bool:
        """Verify that manage.py belongs to a real Django project."""
        try:
            content = manage_py.read_text()
            return "django.core.management" in content
        except Exception:
            return False

    def _extract_project_name(self, manage_py: Path) -> None:
        """Extract project name from manage.py."""
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

    def _detect_apps(self) -> List[Dict[str, Any]]:
        """Detect all Django apps in the project with detailed info."""
        apps = []

        try:
            for item in self.path.iterdir():
                if not item.is_dir() or item.name.startswith("."):
                    continue

                # Check if it's a Django app
                is_app = (item / "apps.py").exists() or (item / "models.py").exists()
                if not is_app:
                    continue

                is_installed = self._is_in_installed_apps(item.name)

                apps.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "has_models": (item / "models.py").exists(),
                        "has_admin": (item / "admin.py").exists(),
                        "has_views": (item / "views.py").exists(),
                        "has_urls": (item / "urls.py").exists(),
                        "has_templates": (item / "templates").exists(),
                        "has_migrations": (item / "migrations").exists(),
                        "is_installed": is_installed,
                        "models_count": self._count_app_models(item),
                    }
                )
        except Exception:
            pass

        return apps

    def _count_app_models(self, app_path: Path) -> int:
        """Count models in a specific app."""
        count = 0
        try:
            models_file = app_path / "models.py"
            if models_file.exists():
                content = models_file.read_text()
                matches = re.findall(r"class\s+(\w+)\(.*models\.Model", content)
                count = len(matches)
        except Exception:
            pass
        return count

    def _is_in_installed_apps(self, app_name: str) -> bool:
        """Check if app is in INSTALLED_APPS."""
        try:
            settings_path = self._find_settings_path()
            if settings_path and settings_path.exists():
                content = settings_path.read_text()
                return f"'{app_name}'" in content or f'"{app_name}"' in content
        except Exception:
            pass
        return False

    def _find_settings_path(self) -> Optional[Path]:
        """Find settings.py file."""
        settings_path = (
            self.path / self.project_info.get("project_name", "") / "settings.py"
        )
        if settings_path.exists():
            return settings_path

        settings_path = self.path / "settings.py"
        if settings_path.exists():
            return settings_path

        # Search in subdirectories
        for path in self.path.glob("*/settings.py"):
            return path

        return None

    def _check_migrations_needed(self) -> bool:
        """Check if there are model changes without migrations."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "manage.py", "makemigrations", "--dry-run"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "No changes detected" not in result.stdout and result.returncode == 0
        except Exception:
            return False

    def _check_server_running(self) -> bool:
        """Check if Django development server is running."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", 8000))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _check_venv(self) -> bool:
        """Check if virtual environment is active."""
        return bool(os.environ.get("VIRTUAL_ENV")) or bool(
            os.environ.get("UV_PROJECT_ENVIRONMENT")
        )

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
                count += app.get("models_count", 0)
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
                timeout=10,
            )
            if result.returncode == 0:
                unapplied = []
                for line in result.stdout.split("\n"):
                    if "[ ]" in line and not line.strip().startswith("["):
                        # Clean up the line
                        clean_line = line.replace("[ ]", "").strip()
                        if clean_line:
                            unapplied.append(clean_line)
                return unapplied
        except Exception:
            pass
        return []

    def _check_admin_enabled(self) -> bool:
        """Check if admin interface is enabled."""
        try:
            urls_path = (
                self.path / self.project_info.get("project_name", "") / "urls.py"
            )
            if not urls_path.exists():
                urls_path = self.path / "urls.py"

            if urls_path.exists():
                content = urls_path.read_text()
                return "admin.site.urls" in content
        except Exception:
            pass
        return False

    def _check_static_files(self) -> bool:
        """Check if static directory exists."""
        static_dir = self.path / "static"
        return static_dir.exists()

    def _check_media_files(self) -> bool:
        """Check if media directory exists."""
        media_dir = self.path / "media"
        return media_dir.exists()

    def get_status_dashboard(self) -> str:
        """Generate a beautiful status dashboard."""
        if not self.is_django_project:
            return "Not a Django project"

        # Safe string formatting with fallbacks
        project_name = str(self.project_info.get("project_name", "Unknown"))[:40]
        git_branch = str(self.project_info.get("git_branch", "N/A"))[:40]
        venv_status = (
            "✅ Active" if self.project_info.get("venv_active") else "❌ Inactive"
        )
        server_status = (
            "🟢 Running" if self.project_info.get("server_running") else "⚫ Stopped"
        )
        apps_count = str(len(self.project_info.get("apps", [])))
        models_count = str(self.project_info.get("models_count", 0))
        needs_migrations = (
            "⚠️ Needed" if self.project_info.get("needs_migrations") else "✅ Up to date"
        )
        unapplied_count = str(len(self.project_info.get("unapplied_migrations", [])))
        admin_status = (
            "✅ Enabled" if self.project_info.get("has_admin") else "❌ Disabled"
        )

        status = f"""
╭─────────────────────────────────────────────────────────────────╮
│                    📊 DJANGO PROJECT STATUS                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📁 Project:     {project_name:<40} │
│  🌿 Branch:      {git_branch:<40} │
│  🐍 VirtualEnv:  {venv_status:<40} │
│  🖥️  Server:      {server_status:<40} │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  📦 Apps:        {apps_count:<40} │
│  🗄️  Models:      {models_count:<40} │
│  👑 Admin:       {admin_status:<40} │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  📝 Migrations:  {needs_migrations:<40} │
│  ⏳ Pending:     {unapplied_count:<40} │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯
"""
        return status

    def get_apps_table(self) -> List[Tuple[str, str, str, str, str]]:
        """Get formatted apps list for table display."""
        apps_table = []
        for app in self.project_info.get("apps", []):
            status = "✅ Installed" if app.get("is_installed") else "⚠️ Not in settings"
            apps_table.append(
                (
                    app.get("name", "Unknown"),
                    "✓" if app.get("has_models") else "✗",
                    "✓" if app.get("has_admin") else "✗",
                    "✓" if app.get("has_urls") else "✗",
                    status,
                )
            )
        return apps_table

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary dictionary of project state."""
        return {
            "is_django": self.is_django_project,
            "name": self.project_info.get("project_name"),
            "branch": self.project_info.get("git_branch"),
            "apps_count": len(self.project_info.get("apps", [])),
            "models_count": self.project_info.get("models_count", 0),
            "needs_migrations": self.project_info.get("needs_migrations", False),
            "unapplied_migrations": len(
                self.project_info.get("unapplied_migrations", [])
            ),
            "server_running": self.project_info.get("server_running", False),
            "venv_active": self.project_info.get("venv_active", False),
        }


class SmartDjangoCLI:
    """Smart CLI for Django project management with contextual commands."""

    def __init__(self, detector: DjangoProjectDetector):
        """
        Initialize the smart CLI.

        Args:
            detector: DjangoProjectDetector instance
        """
        self.detector = detector

    def get_commands(self) -> List[Dict[str, str]]:
        """
        Get available commands based on project state.

        Returns:
            List of command dictionaries with name, action, and description
        """
        commands: List[Dict[str, str]] = [
            {
                "name": "🏃 Run Server",
                "action": "runserver",
                "description": "Start development server",
                "icon": "🖥️",
            },
            {
                "name": "🔄 Make Migrations",
                "action": "makemigrations",
                "description": "Create new migrations",
                "icon": "📝",
            },
            {
                "name": "⚙️ Migrate",
                "action": "migrate",
                "description": "Apply migrations",
                "icon": "🔄",
            },
            {
                "name": "👤 Create Superuser",
                "action": "createsuperuser",
                "description": "Create admin user",
                "icon": "👑",
            },
            {
                "name": "🧪 Run Tests",
                "action": "test",
                "description": "Run all tests",
                "icon": "✅",
            },
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
            {
                "name": "🗑️ Manage Apps",
                "action": "manage_apps",
                "description": "Add/remove installed apps",
                "icon": "⚙️",
            },
        ]

        # Highlight needed actions based on state
        if self.detector.project_info.get("needs_migrations"):
            commands.insert(
                1,
                {
                    "name": "⚠️ Make Migrations (Needed!)",
                    "action": "makemigrations",
                    "description": "Model changes detected! Run this first",
                    "icon": "⚠️",
                },
            )

        unapplied = len(self.detector.project_info.get("unapplied_migrations", []))
        if unapplied > 0:
            commands.insert(
                2,
                {
                    "name": f"⚠️ Migrate ({unapplied} pending)",
                    "action": "migrate",
                    "description": f"Apply {unapplied} pending migration(s)",
                    "icon": "⚠️",
                },
            )

        return commands

    def get_contextual_help(self) -> str:
        """Get contextual help message based on project state."""
        if not self.detector.is_django_project:
            return "Not in a Django project. Run 'ajo' to create a new project."

        summary = self.detector.get_summary()

        help_parts = []

        if summary["needs_migrations"]:
            help_parts.append("⚠️ You have model changes that need migrations")

        if summary["unapplied_migrations"] > 0:
            help_parts.append(
                f"⚠️ You have {summary['unapplied_migrations']} unapplied migrations"
            )

        if not summary["server_running"]:
            help_parts.append("💡 Server is not running. Use 'Run Server' to start it")

        if summary["apps_count"] == 0:
            help_parts.append(
                "💡 No apps detected. Use 'Create New App' to get started"
            )

        if help_parts:
            return "\n".join(help_parts)

        return "✅ Project looks healthy! Choose a command to get started"
