"""Plugin hook system — lifecycle hooks for the scaffold pipeline.

Plugins can advertise ``pre_scaffold`` and/or ``post_scaffold`` hooks in
their ``addon.json`` manifest.  Each hook points to a Python callable
(via the ``entry_point`` field, in ``module:function`` format) that is
imported and invoked at the appropriate point in the scaffold pipeline.

The :class:`PluginManager` is the primary coordinator: it combines
discovery, validation, hook loading, and hook execution into a single
interface used by the :class:`~ajo.scaffolding.engine.ScaffoldEngine`.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Any

from ajo.plugins.discovery import PluginDiscovery
from ajo.plugins.exceptions import PluginHookError
from ajo.plugins.manifest import ManifestValidator, PluginManifest

logger = logging.getLogger(__name__)

# ── Hook types ────────────────────────────────────────────────────────────────


class HookType(str, Enum):
    """Standard hook types that plugins may implement."""

    PRE_SCAFFOLD = "pre_scaffold"
    POST_SCAFFOLD = "post_scaffold"


# ── Hook signature ────────────────────────────────────────────────────────────

#: Signature for a hook callable.
#: May be sync or async.
HookFunc = Callable[
    [Path, dict[str, Any]],
    None | Awaitable[None],
]

#: Registry entry mapping hook type → loaded callable.
HookRegistry = dict[HookType, HookFunc]


# ── Entry-point loader ────────────────────────────────────────────────────────


def _load_hook_callable(
    manifest: PluginManifest,
) -> HookRegistry | None:
    """Load a plugin's hook callables from its ``entry_point``.

    The entry point format is ``module:function`` where *module* is a
    Python module path relative to the plugin directory and *function*
    is the name of a callable that receives ``(project_path, env_config)``.

    If the plugin advertises ``pre_scaffold`` and/or ``post_scaffold`` in
    its ``hooks`` list, the loaded function must be the entry point for
    **both** hooks (single function called for both phases).

    Uses file-based import with a unique module name to avoid conflicts
    with the system module cache.
    """
    if not manifest.entry_point:
        logger.debug(
            "Plugin %r has hooks %r but no entry_point — skipping",
            manifest.name,
            manifest.hooks,
        )
        return None

    if not manifest.hooks:
        return None

    try:
        # Parse "module:function" or just "module"
        parts = manifest.entry_point.split(":")
        module_path = parts[0]
        func_name = parts[1] if len(parts) > 1 else "run_hook"
    except (IndexError, ValueError):
        logger.warning(
            "Invalid entry_point %r for plugin %r", manifest.entry_point, manifest.name
        )
        return None

    plugin_dir = manifest.path
    if plugin_dir is None:
        logger.warning(
            "Plugin %r has no path set — cannot import entry_point",
            manifest.name,
        )
        return None

    # Build the absolute file path for the module
    module_file = plugin_dir / f"{module_path}.py"
    if not module_file.is_file():
        logger.warning(
            "Plugin %r: entry_point module file %r not found",
            manifest.name,
            str(module_file),
        )
        return None

    # Use a unique module name to avoid sys.modules collisions
    safe_name = manifest.name.replace("-", "_").replace(".", "_")
    unique_module_name = f"_ajo_plugin_{safe_name}_{module_path.replace('.', '_')}"
    old_module: Any = None

    try:
        # Load the module from the specific file path
        old_module = sys.modules.get(unique_module_name)
        spec = importlib.util.spec_from_file_location(
            unique_module_name,
            str(module_file),
        )
        if spec is None or spec.loader is None:
            logger.warning(
                "Plugin %r: could not create spec for %r",
                manifest.name,
                str(module_file),
            )
            return None

        mod = importlib.util.module_from_spec(spec)
        # Store in sys.modules temporarily so relative imports work
        old_module = sys.modules.get(unique_module_name)
        sys.modules[unique_module_name] = mod

        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            logger.warning(
                "Plugin %r: error executing module %r: %s",
                manifest.name,
                str(module_file),
                exc,
            )
            return None

        func: Any = getattr(mod, func_name, None)
        if func is None:
            logger.warning(
                "Plugin %r: entry_point %r refers to missing function %r in module %r",
                manifest.name,
                manifest.entry_point,
                func_name,
                module_path,
            )
            return None

        if not callable(func):
            logger.warning(
                "Plugin %r: entry_point %r is not callable",
                manifest.name,
                manifest.entry_point,
            )
            return None

        # Map advertised hook types to the same callable
        registry: HookRegistry = {}
        for hook_type_str in manifest.hooks:
            try:
                hook_type = HookType(hook_type_str)
                registry[hook_type] = func
            except ValueError:
                logger.debug(
                    "Unknown hook type %r in plugin %r", hook_type_str, manifest.name
                )

        return registry

    except Exception as exc:
        logger.warning(
            "Plugin %r: unexpected error loading entry_point %r: %s",
            manifest.name,
            manifest.entry_point,
            exc,
        )
        return None
    finally:
        # Clean up sys.modules to avoid polluting the namespace
        if unique_module_name in sys.modules:
            if old_module is not None:
                sys.modules[unique_module_name] = old_module
            else:
                del sys.modules[unique_module_name]


# ── Plugin manager ────────────────────────────────────────────────────────────

_SCAFFOLD_HOOK_ORDER = [HookType.PRE_SCAFFOLD, HookType.POST_SCAFFOLD]
"""Execution order for scaffold lifecycle hooks."""


class PluginManager:
    """Orchestrates plugin discovery, validation, hook loading, and execution.

    This is the primary integration point with the scaffold pipeline.

    Usage::

        mgr = PluginManager()
        errors = mgr.load_all()
        if not errors:
            await mgr.execute_pre_scaffold(project_path, env_config)
            # ... scaffold pipeline ...
            await mgr.execute_post_scaffold(project_path, env_config)
    """

    def __init__(
        self,
        discovery: PluginDiscovery | None = None,
    ) -> None:
        self._discovery = discovery or PluginDiscovery()
        self._manifests: list[PluginManifest] = []
        self._hook_registries: dict[str, HookRegistry] = {}
        """Mapping of plugin name → {hook_type: callable}."""
        self._load_errors: list[PluginHookError] = []

    # ── Public API ───────────────────────────────────────────────────────

    def load_all(self) -> list[PluginHookError]:
        """Discover plugins, validate manifests, and load hook callables.

        Returns:
            A list of :class:`PluginHookError` instances for any plugins
            that failed to load.  An empty list means all loaded OK.
        """
        self._manifests.clear()
        self._hook_registries.clear()
        self._load_errors.clear()

        # Phase 1: discover + validate
        discovery_result = self._discovery.scan()
        self._manifests = discovery_result.manifests

        # Convert discovery errors to hook errors
        for err in discovery_result.errors:
            self._load_errors.append(
                PluginHookError(
                    str(err),
                    plugin_name="<unknown>",
                    hook_type="discovery",
                )
            )

        # Phase 2: load hook callables for each manifest
        for manifest in self._manifests:
            if not manifest.hooks:
                continue  # Plugin has no hooks, nothing to load

            registry = _load_hook_callable(manifest)
            if registry is None:
                self._load_errors.append(
                    PluginHookError(
                        f"Failed to load hook callable for plugin {manifest.name!r}",
                        plugin_name=manifest.name,
                        hook_type=",".join(manifest.hooks),
                    )
                )
                continue

            self._hook_registries[manifest.name] = registry
            logger.info(
                "Loaded hooks for plugin %r: %s",
                manifest.name,
                list(registry.keys()),
            )

        return list(self._load_errors)

    async def execute_pre_scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> list[PluginHookError]:
        """Execute all loaded ``pre_scaffold`` hooks.

        Args:
            project_path: Target project directory.
            env_config: Project configuration dict.

        Returns:
            List of errors from failed hooks (empty = all succeeded).
        """
        return await self._execute_hook_type(
            HookType.PRE_SCAFFOLD,
            project_path,
            env_config,
        )

    async def execute_post_scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> list[PluginHookError]:
        """Execute all loaded ``post_scaffold`` hooks.

        Args:
            project_path: Target project directory.
            env_config: Project configuration dict.

        Returns:
            List of errors from failed hooks (empty = all succeeded).
        """
        return await self._execute_hook_type(
            HookType.POST_SCAFFOLD,
            project_path,
            env_config,
        )

    @property
    def manifests(self) -> list[PluginManifest]:
        """Discovered and validated plugin manifests."""
        return list(self._manifests)

    @property
    def load_errors(self) -> list[PluginHookError]:
        """Errors from the most recent :meth:`load_all` call."""
        return list(self._load_errors)

    # ── Internal ─────────────────────────────────────────────────────────

    async def _execute_hook_type(
        self,
        hook_type: HookType,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> list[PluginHookError]:
        """Execute all hooks of a given type across all loaded plugins.

        Plugins are executed in discovery order.  Each hook is called
        independently so a failure in one does not prevent others from
        running.
        """
        errors: list[PluginHookError] = []

        for manifest in self._manifests:
            registry = self._hook_registries.get(manifest.name)
            if registry is None:
                continue

            func = registry.get(hook_type)
            if func is None:
                continue

            try:
                result = func(project_path, env_config)
                if isinstance(result, Awaitable):
                    await result
                logger.debug(
                    "Hook %s for plugin %r completed",
                    hook_type.value,
                    manifest.name,
                )
            except Exception as exc:
                err = PluginHookError(
                    f"Plugin {manifest.name!r} {hook_type.value} hook failed: {exc}",
                    plugin_name=manifest.name,
                    hook_type=hook_type.value,
                    original=exc,
                )
                errors.append(err)
                logger.warning(str(err))

        return errors


__all__ = [
    "HookType",
    "HookFunc",
    "HookRegistry",
    "PluginManager",
]
