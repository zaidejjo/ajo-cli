"""Utility functions for security and file operations."""

import secrets
import string
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


def generate_secure_key(length: int = 50) -> str:
    """Generate a cryptographically secure secret key."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


def rollback_project(project_path: Path) -> bool:
    """
    Safely remove project directory on failure.

    Returns:
        True if successful, False otherwise
    """
    try:
        if project_path.exists():
            shutil.rmtree(project_path)
            console.print(f"[dim]✓ Removed {project_path}[/dim]")
        return True
    except Exception as e:
        console.print(f"[red]Failed to rollback: {e}[/red]")
        return False


def append_to_installed_apps(settings_path: Path, app_name: str) -> bool:
    """
    Add app to INSTALLED_APPS in settings.py.

    Returns:
        True if successful, False otherwise
    """
    try:
        content = settings_path.read_text()
        search = f"'{app_name}'"

        if search in content:
            return True  # Already exists

        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "INSTALLED_APPS = [" in line:
                # Find the end of the list
                bracket_count = 0
                inserted = False

                for j in range(i, len(lines)):
                    if "]" in lines[j] and bracket_count == 0:
                        lines.insert(j, f"    '{app_name}',")
                        inserted = True
                        break
                    bracket_count += lines[j].count("[")
                    bracket_count -= lines[j].count("]")

                if not inserted:
                    # Fallback: append at the end of list
                    lines.insert(i + 1, f"    '{app_name}',")
                break

        settings_path.write_text("\n".join(lines))
        return True
    except Exception as e:
        console.print(f"[red]Failed to update settings: {e}[/red]")
        return False


def check_uv_installed() -> bool:
    """Check if uv is installed on the system."""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_uv_version() -> Optional[str]:
    """Get uv version if installed."""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
