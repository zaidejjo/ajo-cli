"""Validation utilities for project and app names, plus self-healing diagnostics.

This module houses:

* :class:`ProjectNameValidator` / :class:`AppNameValidator` — name validation.
* :class:`DiagnosticIssue` — data container for a discovered problem.
* :class:`DiagnosticEngine` — scans a Django project for common misconfigurations
  (missing ``INSTALLED_APPS``, migration conflicts, missing ``SECRET_KEY``, etc.)
  and offers automated fixes via ``auto_fix`` callables.
"""

from __future__ import annotations

import keyword
import re
import secrets
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Final


# =============================================================================
# NAME VALIDATORS (existing)
# =============================================================================


class ProjectNameValidator:
    """Validate Django project names."""

    RESERVED_NAMES: Final[frozenset[str]] = frozenset(
        {
            "test",
            "django",
            "python",
            "site",
            "config",
            "settings",
            "urls",
            "wsgi",
            "asgi",
            "manage",
            "admin",
            "app",
            "project",
        }
    )

    @classmethod
    def validate(cls, name: str) -> tuple[bool, str]:
        """
        Validate project name.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or len(name.strip()) == 0:
            return False, "Project name cannot be empty"

        name = name.strip()

        # Check length
        if len(name) > 50:
            return False, "Project name too long (max 50 characters)"

        # Check first character
        if not name[0].isalpha() and name[0] != "_":
            return False, "Project name must start with a letter or underscore"

        # Check allowed characters
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            return False, (
                "Project name can only contain letters, numbers, and underscores"
            )

        # Check Python keywords
        if keyword.iskeyword(name):
            return False, f"'{name}' is a Python keyword and cannot be used"

        # Check reserved names
        if name.lower() in cls.RESERVED_NAMES:
            return False, f"'{name}' is a reserved name in Django"

        return True, ""

    @classmethod
    def sanitize(cls, desired_name: str) -> str:
        """Convert any string to a valid Django project name."""
        name = desired_name.strip().lower()

        # Replace invalid chars with underscore
        name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Remove multiple underscores
        name = re.sub(r"_+", "_", name)

        # Remove leading/trailing underscores
        name = name.strip("_")

        # Must start with letter
        if name and name[0].isdigit():
            name = f"project_{name}"

        # Handle empty name
        if not name:
            name = "myproject"

        # Handle reserved names
        if name in cls.RESERVED_NAMES:
            name = f"{name}_app"

        # Handle keywords
        if keyword.iskeyword(name):
            name = f"{name}_project"

        return name


class AppNameValidator:
    """Validate Django app names."""

    RESERVED_NAMES: Final[frozenset[str]] = frozenset(
        {
            "test",
            "django",
            "python",
            "site",
            "config",
            "settings",
            "urls",
            "wsgi",
            "asgi",
            "manage",
            "admin",
        }
    )

    @classmethod
    def validate(cls, name: str) -> tuple[bool, str]:
        """Validate app name."""
        if not name or len(name.strip()) == 0:
            return False, "App name cannot be empty"

        name = name.strip()

        if len(name) > 50:
            return False, "App name too long (max 50 characters)"

        if not name[0].isalpha():
            return False, "App name must start with a letter"

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            return False, (
                "App name can only contain letters, numbers, and underscores"
            )

        if keyword.iskeyword(name):
            return False, f"'{name}' is a Python keyword"

        if name.lower() in cls.RESERVED_NAMES:
            return False, f"'{name}' is a reserved name in Django"

        return True, ""


# =============================================================================
# DIAGNOSTIC ENGINE — Self-Healing Diagnostics
# =============================================================================


@dataclass
class DiagnosticIssue:
    """A single discovered issue in a Django project.

    Attributes:
        severity: ``"error"``, ``"warning"``, or ``"info"``.
        category: Issue category (e.g. ``"installed_apps"``, ``"migrations"``,
            ``"settings"``).
        message: Human-readable description of the issue.
        file_path: Path to the affected file, if any.
        fix_description: Short description of what the auto-fix will do.
        auto_fix: A zero-argument callable that attempts to fix the issue
            and returns ``True`` on success.
    """

    severity: str = "warning"
    category: str = "general"
    message: str = ""
    file_path: Path | None = None
    fix_description: str = ""
    auto_fix: Callable[[], bool] | None = None


class DiagnosticEngine:
    """Scan a Django project directory for common issues and offer fixes.

    .. rubric:: Checks performed

    1. **INSTALLED_APPS** — verifies all required Django contrib apps are
       present in ``settings.py``.
    2. **Migration conflicts** — detects duplicate migration number prefixes
       in any ``migrations/`` directory.
    3. **Settings integrity** — checks for ``ALLOWED_HOSTS``,
       ``SECRET_KEY``, and safe ``DEBUG`` defaults.
    4. **Url patterns** — verifies ``admin/`` is wired in the root URLconf.

    Each detected issue carries an optional ``auto_fix`` callable that can
    programmatically resolve it.

    Usage::

        engine = DiagnosticEngine(project_path)
        issues = engine.run_full_diagnostic()
        for issue in issues:
            if issue.auto_fix and user_confirms:
                issue.auto_fix()
    """

    #: Django contrib apps that should always be present.
    REQUIRED_APPS: Final[frozenset[str]] = frozenset(
        {
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        }
    )

    #: ``settings.py`` filename variants (project-level or single-file).
    SETTINGS_FILENAMES: Final[list[str]] = [
        "settings.py",
        "settings/base.py",
        "settings/local.py",
        "settings/production.py",
    ]

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path.resolve()
        self.issues: list[DiagnosticIssue] = []
        self._settings_content: str | None = None
        self._settings_path: Path | None = None
        self._project_name: str | None = None

    # ── Public API ───────────────────────────────────────────────────────

    def run_full_diagnostic(self) -> list[DiagnosticIssue]:
        """Execute all diagnostic checks and return the issue list.

        Returns:
            A list of :class:`DiagnosticIssue` instances (may be empty).
        """
        self.issues.clear()
        self._locate_settings()

        self._check_installed_apps()
        self._check_migration_conflicts()
        self._check_settings_integrity()
        self._check_secret_key()
        self._check_urls_admin()

        return self.issues

    def has_errors(self) -> bool:
        """``True`` if any issue has severity ``"error"``."""
        return any(i.severity == "error" for i in self.issues)

    def has_warnings(self) -> bool:
        """``True`` if any issue has severity ``"warning"``."""
        return any(i.severity == "warning" for i in self.issues)

    # ── Settings file discovery ──────────────────────────────────────────

    def _locate_settings(self) -> None:
        """Find the project's ``settings.py`` file."""
        for candidate in self.SETTINGS_FILENAMES:
            path = self.project_path / candidate
            if path.is_file():
                self._settings_path = path
                self._settings_content = path.read_text(
                    encoding="utf-8", errors="replace"
                )
                # Extract project name from path
                parts = path.relative_to(self.project_path).parts
                if len(parts) > 1:
                    self._project_name = parts[0]
                return

        # Fallback: glob search
        for path in self.project_path.glob("**/settings.py"):
            # Skip venv and .venv
            rel = path.relative_to(self.project_path)
            if any(p.startswith(".") or p in ("venv", ".venv") for p in rel.parts):
                continue
            self._settings_path = path
            self._settings_content = path.read_text(encoding="utf-8", errors="replace")
            return

    # ── Check: INSTALLED_APPS ────────────────────────────────────────────

    def _check_installed_apps(self) -> None:
        """Verify that all required contrib apps are in INSTALLED_APPS."""
        if not self._settings_content or self._settings_path is None:
            return

        settings_name = self._settings_path.name
        for app in self.REQUIRED_APPS:
            if app not in self._settings_content:
                self.issues.append(
                    DiagnosticIssue(
                        severity="error",
                        category="installed_apps",
                        message=(
                            f"App '{app}' is missing from INSTALLED_APPS "
                            f"in {settings_name}"
                        ),
                        file_path=self._settings_path,
                        auto_fix=self._make_auto_add_app(app),
                        fix_description=f"Add '{app}' to INSTALLED_APPS",
                    )
                )

    def _make_auto_add_app(self, app: str) -> Callable[[], bool]:
        """Return a closure that adds *app* to INSTALLED_APPS."""
        path = self._settings_path
        content = self._settings_content

        def _fix() -> bool:
            if path is None or content is None:
                return False
            try:
                new_content = content.replace(
                    "INSTALLED_APPS = [",
                    f"INSTALLED_APPS = [\n    '{app}',",
                    1,
                )
                # If the above didn't change anything, try bracket on next line
                if new_content == content:
                    new_content = content.replace(
                        "INSTALLED_APPS = [\n",
                        f"INSTALLED_APPS = [\n    '{app}',\n",
                        1,
                    )
                path.write_text(new_content, encoding="utf-8")
                return True
            except (OSError, PermissionError):
                return False

        return _fix

    # ── Check: Migration conflicts ───────────────────────────────────────

    def _check_migration_conflicts(self) -> None:
        """Detect duplicate migration number prefixes."""
        try:
            for child in self.project_path.iterdir():
                if not child.is_dir() or child.name.startswith("."):
                    continue
                migrations_dir = child / "migrations"
                if not migrations_dir.is_dir():
                    continue

                seen_numbers: set[str] = set()
                for mf in sorted(migrations_dir.glob("[0-9]*.py")):
                    prefix = mf.stem.split("_")[0]
                    if prefix in seen_numbers:
                        self.issues.append(
                            DiagnosticIssue(
                                severity="error",
                                category="migrations",
                                message=(
                                    f"Migration conflict in {child.name}: "
                                    f"{mf.name} has duplicate prefix '{prefix}'"
                                ),
                                file_path=mf,
                                auto_fix=self._make_auto_rename_migration(mf, prefix),
                                fix_description=f"Rename {mf.name} to fix prefix",
                            )
                        )
                    seen_numbers.add(prefix)
        except PermissionError:
            pass

    @staticmethod
    def _make_auto_rename_migration(
        mf: Path,
        prefix: str,
    ) -> Callable[[], bool]:
        """Return a closure that renames a migration file with a new prefix."""

        def _fix() -> bool:
            try:
                # Find the next available number
                parent = mf.parent
                existing = [
                    int(p.stem.split("_")[0])
                    for p in parent.glob("[0-9]*.py")
                    if p.stem.split("_")[0].isdigit()
                ]
                next_num = max(existing) + 1 if existing else 1
                new_name = f"{next_num:04d}_{mf.stem.split('_', 1)[-1]}{mf.suffix}"
                mf.rename(parent / new_name)
                return True
            except (OSError, PermissionError):
                return False

        return _fix

    # ── Check: Settings integrity ────────────────────────────────────────

    def _check_settings_integrity(self) -> None:
        """Check for missing or misconfigured settings."""
        if not self._settings_content or self._settings_path is None:
            return

        settings_name = self._settings_path.name
        # ALLOWED_HOSTS
        if "ALLOWED_HOSTS" not in self._settings_content:
            self.issues.append(
                DiagnosticIssue(
                    severity="warning",
                    category="settings",
                    message=(f"ALLOWED_HOSTS is not defined in {settings_name}"),
                    file_path=self._settings_path,
                    auto_fix=self._make_auto_add_allowed_hosts(),
                    fix_description="Add ALLOWED_HOSTS = ['*'] (dev only)",
                )
            )

        # DEBUG check (ensure it's not hard-coded to True in production-like settings)
        debug_match = re.search(
            r"DEBUG\s*=\s*(True|False)",
            self._settings_content,
        )
        if debug_match and debug_match.group(1) == "True":
            # Only warn if in a non-local settings file
            if "local" not in settings_name and "dev" not in settings_name:
                self.issues.append(
                    DiagnosticIssue(
                        severity="warning",
                        category="settings",
                        message=(
                            "DEBUG is set to True in "
                            f"{settings_name} — "
                            "ensure this is not pushed to production"
                        ),
                        file_path=self._settings_path,
                    )
                )

    def _check_secret_key(self) -> None:
        """Check that a SECRET_KEY exists and isn't a placeholder."""
        if not self._settings_content or self._settings_path is None:
            return

        settings_name = self._settings_path.name
        if "SECRET_KEY" not in self._settings_content:
            self.issues.append(
                DiagnosticIssue(
                    severity="error",
                    category="settings",
                    message=(f"SECRET_KEY is missing from {settings_name}"),
                    file_path=self._settings_path,
                    auto_fix=self._make_auto_generate_secret_key(),
                    fix_description="Generate a secure random SECRET_KEY",
                )
            )
        else:
            # Check for placeholder keys
            for placeholder in ("CHANGE_ME", "your-secret", "secret-key", "change-me"):
                if placeholder in self._settings_content:
                    self.issues.append(
                        DiagnosticIssue(
                            severity="warning",
                            category="settings",
                            message=(
                                f"SECRET_KEY contains placeholder '{placeholder}' "
                                f"in {settings_name}"
                            ),
                            file_path=self._settings_path,
                            auto_fix=self._make_auto_generate_secret_key(),
                            fix_description="Replace placeholder with a secure key",
                        )
                    )
                    break

    def _check_urls_admin(self) -> None:
        """Check that admin URLs are wired in the root URLconf."""
        urls_path = self._find_urls_file()
        if urls_path is None:
            return

        try:
            content = urls_path.read_text(encoding="utf-8", errors="replace")
            if "admin.site.urls" not in content:
                self.issues.append(
                    DiagnosticIssue(
                        severity="info",
                        category="settings",
                        message=(
                            f"admin/ URLs not found in {urls_path.name} "
                            "(optional for API-only projects)"
                        ),
                        file_path=urls_path,
                        auto_fix=self._make_auto_add_admin_url(urls_path, content),
                        fix_description="Add admin/ path to urlpatterns",
                    )
                )
        except (OSError, PermissionError):
            pass

    def _find_urls_file(self) -> Path | None:
        """Locate the project's root ``urls.py``."""
        if self._project_name:
            path = self.project_path / self._project_name / "urls.py"
            if path.is_file():
                return path
        # Fallback: look for urls.py next to settings
        if self._settings_path:
            sibling = self._settings_path.parent / "urls.py"
            if sibling.is_file():
                return sibling
        # Broader search
        for path in self.project_path.glob("**/urls.py"):
            rel = path.relative_to(self.project_path)
            if any(p.startswith(".") or p in ("venv", ".venv") for p in rel.parts):
                continue
            return path
        return None

    # ── Auto-fix builders ────────────────────────────────────────────────

    def _make_auto_add_allowed_hosts(self) -> Callable[[], bool]:
        """Return a closure that appends ALLOWED_HOSTS to settings."""
        path = self._settings_path

        def _fix() -> bool:
            if path is None:
                return False
            try:
                content = path.read_text(encoding="utf-8")
                new_content = content.rstrip() + '\n\nALLOWED_HOSTS = ["*"]\n'
                path.write_text(new_content, encoding="utf-8")
                return True
            except (OSError, PermissionError):
                return False

        return _fix

    def _make_auto_generate_secret_key(self) -> Callable[[], bool]:
        """Return a closure that generates and inserts a SECRET_KEY."""
        path = self._settings_path

        def _fix() -> bool:
            if path is None:
                return False
            try:
                alphabet = string.ascii_letters + string.digits + string.punctuation
                new_key = "".join(secrets.choice(alphabet) for _ in range(50))
                content = path.read_text(encoding="utf-8")

                if "SECRET_KEY" not in content:
                    # Insert after module docstring or at top
                    new_content = f'import os\nSECRET_KEY = "{new_key}"\n\n{content}'
                else:
                    # Replace placeholder
                    new_content = re.sub(
                        r'SECRET_KEY\s*=\s*["\'].*?["\']',
                        f'SECRET_KEY = "{new_key}"',
                        content,
                    )
                path.write_text(new_content, encoding="utf-8")
                return True
            except (OSError, PermissionError):
                return False

        return _fix

    @staticmethod
    def _make_auto_add_admin_url(
        urls_path: Path,
        content: str,
    ) -> Callable[[], bool]:
        """Return a closure that adds ``admin/`` to urlpatterns."""

        def _fix() -> bool:
            try:
                if "from django.contrib import admin" not in content:
                    new_import = "from django.contrib import admin\n"
                    new_content = new_import + content
                else:
                    new_content = content

                # Find urlpatterns and add admin path
                if "path('admin/" not in new_content:
                    new_content = new_content.replace(
                        "urlpatterns = [",
                        "urlpatterns = [\n    path('admin/', admin.site.urls),",
                        1,
                    )
                urls_path.write_text(new_content, encoding="utf-8")
                return True
            except (OSError, PermissionError):
                return False

        return _fix
