"""Composable add-on module system for ajo-cli.

Add-ons are lightweight, composable feature modules that layer onto
any architecture preset after the main scaffold step.  They handle
settings injection, file generation, and dependency installation.

Usage::

    from ajo.presets.addons import get_addon, resolve_addons

    addons = resolve_addons(["auth", "cache"], preset_key="ninja-api")
    for addon in addons:
        await addon.apply(project_path, project_name, env_config)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

from ajo.core.exceptions import PresetError


# =============================================================================
# Registry
# =============================================================================

ADDON_REGISTRY: dict[str, type["AbstractAddon"]] = {}
"""Mapping of add-on keys (e.g. ``"auth"``, ``"cache"``) to their
concrete :class:`AbstractAddon` subclasses.

Populated by :func:`register_addon` calls at module import time.
"""


def register_addon(
    cls: type["AbstractAddon"],
) -> type["AbstractAddon"]:
    """Decorator / direct-call to register an add-on class.

    The registry key is derived from the class name: ``AuthAddon`` → ``"auth"``.

    Usage::

        @register_addon
        class AuthAddon(AbstractAddon):
            ...
    """
    key = _derive_key(cls)
    if key in ADDON_REGISTRY:
        raise PresetError(
            f"Add-on {key!r} is already registered ({ADDON_REGISTRY[key].__name__})."
        )
    ADDON_REGISTRY[key] = cls
    return cls


def get_addon(key: str) -> type["AbstractAddon"]:
    """Look up an add-on class by its registry key.

    Args:
        key: The registry key (e.g. ``"auth"``).

    Returns:
        The matching add-on class.

    Raises:
        PresetError: If *key* is not found in the registry.
    """
    try:
        return ADDON_REGISTRY[key]
    except KeyError:
        available = ", ".join(sorted(ADDON_REGISTRY))
        raise PresetError(f"Unknown add-on {key!r}. Available: {available}") from None


def resolve_addons(
    selected: list[str],
    preset_key: str | None = None,
) -> list["AbstractAddon"]:
    """Resolve, validate, and order a list of add-on keys.

    Args:
        selected: List of add-on keys (e.g. ``["auth", "cache"]``).
        preset_key: The preset being used (for compatibility checks).

    Returns:
        Ordered list of instantiated add-on objects.

    Raises:
        PresetError: If any add-on is incompatible with the preset
            or conflicts with another selected add-on.
    """
    addons: list[AbstractAddon] = []
    seen: set[str] = set()

    for key in selected:
        cls = get_addon(key)
        instance = cls()

        # Compatibility check
        if (
            preset_key
            and instance.compatible_presets is not None
            and preset_key not in instance.compatible_presets
        ):
            raise PresetError(
                f"Add-on '{key}' is not compatible with preset '{preset_key}'."
            )

        # Conflict check
        for conflict in instance.conflicts_with:
            if conflict in seen:
                raise PresetError(f"Add-on '{key}' conflicts with '{conflict}'.")

        addons.append(instance)
        seen.add(key)

    return addons


def get_addon_choices(
    preset_key: str | None = None,
) -> dict[str, dict[str, str]]:
    """Return available add-ons as a dict for InquirerPy checkbox prompts.

    Filters out add-ons that are incompatible with *preset_key*.

    Returns:
        ``{"auth": {"name": "Auth & Users", "description": "JWT + registration..."}, ...}``
    """
    choices: dict[str, dict[str, str]] = {}
    for key, cls in sorted(ADDON_REGISTRY.items()):
        instance = cls()
        if (
            preset_key
            and instance.compatible_presets is not None
            and preset_key not in instance.compatible_presets
        ):
            continue
        choices[key] = {
            "name": instance.name,
            "description": instance.description,
        }
    return choices


def _derive_key(cls: type["AbstractAddon"]) -> str:
    """Derive the registry key from an add-on class name.

    ``AuthAddon`` → ``"auth"``
    ``CacheAddon`` → ``"cache"``
    """
    name = cls.__name__
    suffix = "Addon"
    if name.endswith(suffix):
        name = name[: -len(suffix)]
    return name.lower()


# =============================================================================
# Abstract Add-on Base Class
# =============================================================================


class AbstractAddon(ABC):
    """Base class for composable feature add-ons.

    Subclasses define what settings to inject, files to generate, and
    dependencies to install when applied to a scaffolded project.

    Usage::

        class AuthAddon(AbstractAddon):
            name = "Auth & Users"
            description = "JWT + registration + profile API"
            dependencies = ["djangorestframework-simplejwt"]
            installed_apps = ["accounts", "rest_framework_simplejwt"]

            async def apply(self, project_path, project_name, env_config):
                await self._inject_settings(project_path)
                await self._wire_urls(project_path, project_name)
                await self._update_env(project_path)
                self._write_file(project_path / "accounts/models.py", ...)
    """

    # ── Metadata (override in subclasses) ─────────────────────────────

    name: str = ""
    """Human-readable name for display in the TUI."""

    description: str = ""
    """One-line description shown in the add-on selection prompt."""

    #: Extra PyPI packages to install (added to ``uv add``).
    dependencies: list[str] = []

    #: Extra dev-only PyPI packages (added to ``uv add --dev``).
    dev_dependencies: list[str] = []

    #: If not ``None``, only these preset registry keys are compatible.
    #: ``None`` means compatible with all presets.
    compatible_presets: list[str] | None = None

    #: Add-on registry keys that conflict with this one.
    conflicts_with: list[str] = []

    # ── Settings / config templates (override in subclasses) ──────────

    #: Dotted app labels to inject into ``INSTALLED_APPS``.
    installed_apps: list[str] = []

    #: Middleware class paths to inject into ``MIDDLEWARE``.
    #: Use ``("path", "first")`` to insert at the beginning,
    #: ``("path", "last")`` to append at the end.
    middleware: list[tuple[str, str | Literal["first", "last"]]] = []

    #: ``(url_path, dotted_import_string)`` tuples for ``urlpatterns``.
    url_patterns: list[tuple[str, str]] = []

    #: Environment variables to add to ``.env`` as ``{KEY: value}``.
    env_vars: dict[str, str] = {}

    #: Raw Python code blocks to append to ``settings.py``.
    settings_blocks: list[str] = []

    # ── Abstract method ───────────────────────────────────────────────

    @abstractmethod
    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Execute add-on scaffolding.

        This method is called **after** the main preset scaffold
        has created the Django project structure.  Implementations
        should:

        * Create additional app directories and files via ``self._write_file()``.
        * Call ``self._inject_settings()`` to modify ``settings.py``.
        * Call ``self._wire_urls()`` to modify ``urls.py``.
        * Call ``self._update_env()`` to extend ``.env``.

        Args:
            project_path: Root directory of the scaffolded project.
            project_name: Django project package name.
            env_config: Project-wide configuration dict (db, secret key, etc.).
        """
        ...

    # ── Concrete helpers ──────────────────────────────────────────────

    async def _inject_settings(self, project_path: Path) -> None:
        """Inject ``installed_apps``, ``middleware``, and
        ``settings_blocks`` into the project's ``settings.py``."""
        from ajo.presets.addons._settings import SettingsInjector

        pkg = self._find_project_package(project_path)
        settings_path = pkg / "settings.py"
        if not settings_path.exists():
            return

        text = settings_path.read_text(encoding="utf-8")

        if self.installed_apps:
            text = SettingsInjector.inject_apps(text, self.installed_apps)

        if self.middleware:
            text = SettingsInjector.inject_middleware(text, self.middleware)  # type: ignore[arg-type]

        for block in self.settings_blocks:
            text = SettingsInjector.append_block(text, block)

        settings_path.write_text(text)

    async def _wire_urls(
        self,
        project_path: Path,
        project_name: str,
    ) -> None:
        """Add ``url_patterns`` to the project's ``urls.py``."""
        from ajo.presets.addons._settings import SettingsInjector

        pkg = self._find_project_package(project_path)
        urls_path = pkg / "urls.py"
        if not urls_path.exists():
            return

        text = urls_path.read_text(encoding="utf-8")
        text = SettingsInjector.inject_urls(text, self.url_patterns)
        urls_path.write_text(text)

    async def _update_env(self, project_path: Path) -> None:
        """Append ``env_vars`` to the project's ``.env``."""
        from ajo.presets.addons._settings import SettingsInjector

        env_path = project_path / ".env"
        if not env_path.exists():
            # Create it with the add-on vars
            env_path.write_text(
                "\n".join(f"{k}={v}" for k, v in self.env_vars.items()) + "\n"
            )
            return

        text = env_path.read_text(encoding="utf-8")
        text = SettingsInjector.inject_env(text, self.env_vars)
        env_path.write_text(text)

    def _write_file(
        self,
        path: Path,
        content: str,
        *,
        overwrite: bool = False,
    ) -> None:
        """Write a file, creating parent directories as needed.

        Args:
            path: Absolute file path.
            content: File content.
            overwrite: If ``False`` (default), do not overwrite
                existing files.
        """
        if path.exists() and not overwrite:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # ── Internal helpers ──────────────────────────────────────────────

    def _find_project_package(self, project_path: Path) -> Path:
        """Find the Django project package directory.

        This is the directory under *project_path* that contains
        ``settings.py`` and ``urls.py``.  Falls back to the
        ``env_config['project_name']`` subdirectory, then the
        project root itself.
        """
        project_name = project_path.name

        # Try ``<project_path>/<project_name>/``
        candidate = project_path / project_name
        if (candidate / "settings.py").exists():
            return candidate

        # Try ``<project_path>/config/`` (alternative naming)
        candidate = project_path / "config"
        if (candidate / "settings.py").exists():
            return candidate

        # Fallback to project root
        return project_path

    def _discover_apps(self, project_path: Path) -> list[str]:
        """Return sorted list of discovered Django app directories.

        An app directory is any subdirectory of *project_path* that
        contains either ``apps.py`` or ``models.py`` (or both).
        """
        apps: list[str] = []
        for child in project_path.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            if (child / "apps.py").exists() or (child / "models.py").exists():
                apps.append(child.name)
        return sorted(apps)


# =============================================================================
# Lazy import add-on implementations (they register themselves)
# =============================================================================

# Importing these modules triggers the @register_addon decorator.
# Each module defines exactly one add-on class.

from ajo.presets.addons.auth import AuthAddon  # noqa: E402, F811
from ajo.presets.addons.cache import CacheAddon  # noqa: E402, F811
from ajo.presets.addons.security import SecurityAddon  # noqa: E402, F811
from ajo.presets.addons.testing import TestingAddon  # noqa: E402, F811

__all__ = [
    "ADDON_REGISTRY",
    "register_addon",
    "get_addon",
    "resolve_addons",
    "get_addon_choices",
    "AbstractAddon",
]
