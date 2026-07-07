"""Plugin-specific exception hierarchy.

All exceptions inherit from :class:`PluginError` which itself inherits from
:class:`~ajo.core.exceptions.AjoError`, ensuring they are caught by top-level
handlers and rendered with user-friendly messages.
"""

from __future__ import annotations

from ajo.core.exceptions import AjoError


class PluginError(AjoError):
    """Base exception for all plugin-related operations."""


class PluginDiscoveryError(PluginError):
    """Raised when a plugin directory or manifest cannot be read.

    This covers permission errors, missing directories, and filesystem
    I/O failures during the discovery scan.
    """

    def __init__(
        self,
        message: str = "",
        *,
        path: str | None = None,
    ) -> None:
        self.path = path
        super().__init__(message)


class PluginValidationError(PluginError):
    """Raised when an ``addon.json`` manifest fails validation.

    Attributes:
        path: Filesystem path to the invalid manifest.
        plugin_name: Name of the plugin (if extractable from the manifest).
        reasons: List of human-readable validation failure descriptions.
    """

    def __init__(
        self,
        message: str = "",
        *,
        path: str | None = None,
        plugin_name: str | None = None,
        reasons: list[str] | None = None,
    ) -> None:
        self.path = path
        self.plugin_name = plugin_name
        self.reasons = reasons or []
        super().__init__(message)


class PluginVersionError(PluginValidationError):
    """Raised when a plugin's version range is incompatible with the
    current ajo version."""


class PluginHookError(PluginError):
    """Raised when a plugin hook callable fails during execution.

    Attributes:
        plugin_name: Name of the plugin whose hook failed.
        hook_type: The hook type (e.g. ``"pre_scaffold"``, ``"post_scaffold"``).
        original: The original exception that caused the hook to fail.
    """

    def __init__(
        self,
        message: str = "",
        *,
        plugin_name: str | None = None,
        hook_type: str | None = None,
        original: Exception | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.hook_type = hook_type
        self.original = original
        super().__init__(message)


__all__ = [
    "PluginError",
    "PluginDiscoveryError",
    "PluginValidationError",
    "PluginVersionError",
    "PluginHookError",
]
