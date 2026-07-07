"""External plugin/add-on discovery and lifecycle management.

This package provides the machinery to discover, validate, and invoke
third-party plugins that extend ajo-cli's scaffolding pipeline.

Plugins are self-contained directories with an ``addon.json`` manifest file.
They can be installed globally under ``~/.config/ajo/addons/`` or locally
under ``<project>/.ajo/addons/``.
"""

from __future__ import annotations

from ajo.plugins.exceptions import (
    PluginDiscoveryError,
    PluginError,
    PluginHookError,
    PluginValidationError,
    PluginVersionError,
)

__all__ = [
    "PluginError",
    "PluginDiscoveryError",
    "PluginValidationError",
    "PluginVersionError",
    "PluginHookError",
]
