"""Custom exceptions for ajo-cli."""


class AJOError(Exception):
    """Base exception for AJO CLI."""

    pass


class ProjectNameError(AJOError):
    """Raised when project name is invalid."""

    pass


class CommandExecutionError(AJOError):
    """Raised when a subprocess command fails."""

    pass


class RollbackError(AJOError):
    """Raised when rollback operation fails."""

    pass
