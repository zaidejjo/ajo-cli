"""Async gateway for ``gh`` (GitHub CLI) operations.

Provides non-blocking wrappers for checking installation status,
authentication state, and repository creation.

All long-running operations (notably ``gh repo create``) have a
``*_streaming`` variant that reports progress via a callback so the
TUI can render a live progress bar.
"""

from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import Callable

from ajo.gateway.utils import _run_command, _run_command_streaming


def gh_check_installed() -> bool:
    """Check whether the ``gh`` CLI is available on ``PATH``.

    Uses :func:`shutil.which` instead of a subprocess call, making
    this effectively free.
    """
    return which("gh") is not None


async def gh_check_auth() -> bool:
    """Check whether the user is authenticated with ``gh``.

    Returns:
        ``True`` if ``gh auth status`` exits successfully.

    Note:
        The underlying subprocess is fast (no network call for cached
        tokens), but still async to avoid blocking the event loop.
    """
    try:
        await _run_command(
            ["gh", "auth", "status"],
            description="gh auth status",
        )
        return True
    except Exception:
        return False


async def gh_repo_create(
    name: str,
    path: Path,
    *,
    private: bool = False,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    """Create a GitHub repository and push the local code to it.

    When *progress_callback* is provided the error stream (where ``gh``
    writes its progress) is piped to the callback line-by-line.

    Equivalent to::

        gh repo create <name> --source=. --remote=origin
            --<private|public> --push --yes

    Args:
        name: Repository name (e.g. ``"my-django-app"``).
        path: Local project root (must be an initialised Git repository
            with at least one commit).
        private: Whether the repository should be private.
        progress_callback: ``(line_number, line_text)`` called for
            every line of stderr (where ``gh`` outputs progress).

    Returns:
        The combined stdout from ``gh repo create``.

    Raises:
        CommandExecutionError: If the ``gh`` command fails.
    """
    visibility = "--private" if private else "--public"
    cmd = [
        "gh",
        "repo",
        "create",
        name,
        "--source=.",
        "--remote=origin",
        visibility,
        "--push",
        "--yes",
    ]

    if progress_callback is not None:
        return await _run_command_streaming(
            cmd,
            cwd=path,
            description=f"gh repo create {name} ({'private' if private else 'public'})",
            progress_callback=progress_callback,
        )
    return await _run_command(
        cmd,
        cwd=path,
        description=f"gh repo create {name} ({'private' if private else 'public'})",
    )
