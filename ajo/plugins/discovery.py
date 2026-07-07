"""Plugin discovery — scanning local directories for external plugins.

The :class:`PluginDiscovery` class searches well-known filesystem locations
for ``addon.json`` manifests, feeds them to the :class:`ManifestValidator`,
and returns validated :class:`PluginManifest` objects.

Directory layout scanned::

    ~/.config/ajo/addons/
    └── <plugin-name>/
        └── addon.json

    <project>/.ajo/addons/
    └── <plugin-name>/
        └── addon.json

The project-local directory (``.ajo/addons/``) takes precedence over the
user-global directory when both contain a plugin with the same name.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ajo.core.config import CONFIG_DIR
from ajo.plugins.exceptions import PluginDiscoveryError, PluginError
from ajo.plugins.manifest import ManifestValidator, PluginManifest

logger = logging.getLogger(__name__)

# ── Default search locations ──────────────────────────────────────────────────

GLOBAL_PLUGIN_DIR: Path = CONFIG_DIR / "addons"
"""``~/.config/ajo/addons/`` — user-wide plugin installation directory."""

LOCAL_PLUGIN_DIR_REL: str = ".ajo/addons"
"""Relative path under a project root for project-scoped plugins."""


# ── Discovery result ──────────────────────────────────────────────────────────


@dataclass
class DiscoveryResult:
    """Aggregated result of a discovery scan.

    Attributes:
        manifests: Plugins that passed validation.
        errors: Per-plugin errors encountered during discovery/validation.
        scanned_dirs: Directories that were scanned.
    """

    manifests: list[PluginManifest] = field(default_factory=list)
    errors: list[PluginDiscoveryError] = field(default_factory=list)
    scanned_dirs: list[Path] = field(default_factory=list)


# ── Discoverer ────────────────────────────────────────────────────────────────


class PluginDiscovery:
    """Scans filesystem locations for external plugins.

    Usage::

        discovery = PluginDiscovery()
        result = discovery.scan()
        for manifest in result.manifests:
            print(f"Found plugin: {manifest.name} v{manifest.version}")
        for error in result.errors:
            print(f"Error: {error}")
    """

    def __init__(
        self,
        *,
        global_dir: Path | None = None,
        project_dir: Path | None = None,
    ) -> None:
        """Initialise the discovery scanner.

        Args:
            global_dir: Override the user-global plugin directory.
                Defaults to ``~/.config/ajo/addons/``.
            project_dir: Override the project-local plugin directory.
                Defaults to ``Path.cwd() / ".ajo/addons/"``.
        """
        self._global_dir: Path = (
            global_dir if global_dir is not None else GLOBAL_PLUGIN_DIR
        )
        self._project_dir: Path = (
            project_dir
            if project_dir is not None
            else Path.cwd() / LOCAL_PLUGIN_DIR_REL
        )
        self._validator = ManifestValidator()

    # ── Public API ───────────────────────────────────────────────────────

    def scan(self) -> DiscoveryResult:
        """Perform a full discovery scan.

        Scans the user-global directory, then the project-local directory.
        Project-local plugins with the same name override global ones.

        Returns:
            A :class:`DiscoveryResult` with validated manifests, per-plugin
            errors, and a list of directories that were scanned.
        """
        result = DiscoveryResult()
        # Dict keyed by plugin name so project-local overrides global
        manifests_by_name: dict[str, PluginManifest] = {}

        # Scan global directory first
        self._scan_directory(self._global_dir, result, manifests_by_name)

        # Scan project-local directory (takes precedence — overrides)
        self._scan_directory(self._project_dir, result, manifests_by_name)

        result.manifests = list(manifests_by_name.values())
        return result

    # ── Internal ─────────────────────────────────────────────────────────

    def _scan_directory(
        self,
        directory: Path,
        result: DiscoveryResult,
        manifests_by_name: dict[str, PluginManifest],
    ) -> None:
        """Scan a single directory for plugin subdirectories.

        Each subdirectory is expected to contain an ``addon.json`` manifest.
        """
        if not directory.is_dir():
            logger.debug("Skipping non-existent plugin directory: %s", directory)
            return

        result.scanned_dirs.append(directory.resolve())

        for plugin_dir in self._iter_plugin_dirs(directory):
            manifest, errors = self._validator.load(plugin_dir)

            if errors:
                for err in errors:
                    result.errors.append(
                        PluginDiscoveryError(
                            str(err),
                            path=str(plugin_dir),
                        )
                    )
                continue

            if manifest is None:
                continue

            # Later scans (project-local) override earlier (global) by name
            manifests_by_name[manifest.name] = manifest
            logger.info(
                "Discovered plugin: %s v%s at %s",
                manifest.name,
                manifest.version,
                plugin_dir,
            )

    @staticmethod
    def _iter_plugin_dirs(directory: Path) -> Iterator[Path]:
        """Iterate over subdirectories that look like plugin directories.

        A plugin directory must contain an ``addon.json`` file
        (not just be any subdirectory).
        """
        try:
            for child in sorted(directory.iterdir()):
                if not child.is_dir():
                    continue
                if child.name.startswith("."):
                    continue
                yield child
        except (OSError, PermissionError) as exc:
            logger.warning("Cannot list plugin directory %s: %s", directory, exc)


__all__ = [
    "GLOBAL_PLUGIN_DIR",
    "LOCAL_PLUGIN_DIR_REL",
    "DiscoveryResult",
    "PluginDiscovery",
]
