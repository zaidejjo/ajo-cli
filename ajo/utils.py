"""Utility functions for security, file operations, and auto-fix helpers.

The auto-fix functions in this module are used by the
:class:`~ajo.validators.DiagnosticEngine` to automatically resolve
common Django project issues.
"""

from __future__ import annotations

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


# =============================================================================
# AUTO-FIX HELPERS (used by DiagnosticEngine)
# =============================================================================


def auto_fix_installed_apps(
    settings_path: Path,
    app_name: str,
) -> bool:
    """Add a missing app to ``INSTALLED_APPS`` in ``settings.py``.

    This is a lower-level helper that performs a direct string replacement
    on the file.  It is used as the ``auto_fix`` callback in
    :class:`~ajo.validators.DiagnosticIssue`.

    Args:
        settings_path: Path to the project's ``settings.py``.
        app_name: The dotted app path to add (e.g. ``"django.contrib.admin"``).

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    return append_to_installed_apps(settings_path, app_name)


def auto_fix_generate_secret_key(settings_path: Path) -> bool:
    """Generate and insert a ``SECRET_KEY`` into ``settings.py``.

    If no ``SECRET_KEY`` line exists, inserts one at the top of the file
    (after any docstring).  If a placeholder exists, replaces it.

    Args:
        settings_path: Path to the project's ``settings.py``.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        import re as _re

        new_key = generate_secure_key(50)
        content = settings_path.read_text(encoding="utf-8")

        if "SECRET_KEY" not in content:
            # Insert after docstring
            if content.startswith('"""'):
                # Find closing quotes
                end_idx = content.find('"""', 3)
                if end_idx != -1:
                    end_idx = content.find("\n", end_idx) + 1
                    new_content = (
                        content[:end_idx]
                        + f'\nSECRET_KEY = "{new_key}"\n'
                        + content[end_idx:]
                    )
                else:
                    new_content = f'SECRET_KEY = "{new_key}"\n' + content
            else:
                new_content = f'SECRET_KEY = "{new_key}"\n' + content
        else:
            # Replace existing key
            new_content = _re.sub(
                r'SECRET_KEY\s*=\s*["\'].*?["\']',
                f'SECRET_KEY = "{new_key}"',
                content,
            )

        settings_path.write_text(new_content, encoding="utf-8")
        return True
    except (OSError, PermissionError):
        return False


def auto_fix_add_allowed_hosts(settings_path: Path) -> bool:
    """Append ``ALLOWED_HOSTS`` to ``settings.py`` if it is missing.

    Args:
        settings_path: Path to the project's ``settings.py``.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        content = settings_path.read_text(encoding="utf-8")
        if "ALLOWED_HOSTS" not in content:
            new_content = content.rstrip() + '\n\nALLOWED_HOSTS = ["*"]\n'
            settings_path.write_text(new_content, encoding="utf-8")
            return True
        return True  # Already present
    except (OSError, PermissionError):
        return False


def auto_fix_add_admin_url(urls_path: Path) -> bool:
    """Add ``admin/`` URL pattern to the root URLconf if missing.

    Args:
        urls_path: Path to the project's root ``urls.py``.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        content = urls_path.read_text(encoding="utf-8")
        if "admin.site.urls" in content:
            return True  # Already wired

        # Add import if missing
        if "from django.contrib import admin" not in content:
            content = "from django.contrib import admin\n" + content

        # Add url pattern
        if "urlpatterns = [" in content:
            content = content.replace(
                "urlpatterns = [",
                "urlpatterns = [\n    path('admin/', admin.site.urls),",
                1,
            )

        urls_path.write_text(content, encoding="utf-8")
        return True
    except (OSError, PermissionError):
        return False


def auto_fix_rename_migration(migration_path: Path) -> bool:
    """Rename a migration file to fix a duplicate prefix.

    Scans the parent directory for the next available migration number
    and renames the file with a unique prefix.

    Args:
        migration_path: Path to the migration file that needs renaming.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        parent = migration_path.parent
        # Find all migration prefixes
        existing: list[int] = []
        for p in parent.glob("[0-9]*.py"):
            stem = p.stem
            parts = stem.split("_", 1)
            if parts[0].isdigit():
                existing.append(int(parts[0]))

        next_num = max(existing) + 1 if existing else 1
        stem = migration_path.stem
        suffix = stem.split("_", 1)[-1] if "_" in stem else stem
        new_name = f"{next_num:04d}_{suffix}{migration_path.suffix}"
        migration_path.rename(parent / new_name)
        return True
    except (OSError, PermissionError):
        return False
