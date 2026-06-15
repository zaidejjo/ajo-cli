"""Robust custom exception hierarchy for ajo-cli.

All exceptions inherit from :exc:`AjoError`, the single public base
class that callers should catch unless they need finer granularity.

Exception tree::

    AjoError
    ├── ProjectNameError        — Invalid project or app name
    ├── CommandExecutionError   — External subprocess failure
    ├── RollbackError           — Rollback operation failure
    ├── StateError              — Invalid state transition or invariant
    └── PresetError             — Preset plugin error or misconfiguration
"""

from typing import Any


class AjoError(Exception):
    """Base exception for all ajo-cli errors.

    All custom exceptions in the application should inherit from this
    class so that top-level handlers can catch ``AjoError`` and render
    a user-friendly message instead of a raw traceback.
    """

    def __init__(self, message: str = "", *args: Any, **kwargs: Any) -> None:
        self.message = message
        super().__init__(message, *args, **kwargs)


# ── Name / Validation ────────────────────────────────────────────────────────


class ProjectNameError(AjoError):
    """Raised when a project or app name fails validation.

    This covers empty names, invalid characters, Python keyword
    collisions, and reserved Django names.
    """


# ── Subprocess / Command ─────────────────────────────────────────────────────


class CommandExecutionError(AjoError):
    """Raised when an external subprocess command fails.

    Attributes:
        command: The command that was executed (as a list of strings).
        return_code: The non-zero exit status of the process.
        stderr: The standard error output from the process.
    """

    def __init__(
        self,
        message: str = "",
        command: list[str] | None = None,
        return_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        self.command = command or []
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(message)


# ── Rollback ─────────────────────────────────────────────────────────────────


class RollbackError(AjoError):
    """Raised when a rollback/cleanup operation fails.

    This is typically caught inside rollback handlers themselves
    so that a best-effort cleanup never propagates and masks the
    original failure.
    """


# ── State management ─────────────────────────────────────────────────────────


class StateError(AjoError):
    """Raised on invalid state transitions or invariant violations.

    Examples:
        - Attempting to scaffold when a project directory already exists.
        - Calling ``create_app`` before the project is scaffolded.
        - A detector method receiving unexpected project structure.
    """


# ── Preset plugins ───────────────────────────────────────────────────────────


class PresetError(AjoError):
    """Raised when an architecture preset plugin fails.

    This covers missing preset classes, invalid preset configuration,
    or errors raised during preset ``post_scaffold`` hooks.
    """
