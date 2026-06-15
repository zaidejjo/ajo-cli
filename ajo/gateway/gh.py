"""Async gateway for ``gh`` (GitHub CLI) operations.

Provides non-blocking wrappers for checking installation status,
authentication state, and repository creation.
"""

from __future__ import annotations

from pathlib import Path
from shutil import which

from ajo.gateway.utils import _run_command


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
) -> str:
    """Create a GitHub repository and push the local code to it.

    Equivalent to::

        gh repo create <name> --source=. --remote=origin
            --<private|public> --push --yes

    Args:
        name: Repository name (e.g. ``"my-django-app"``).
        path: Local project root (must be an initialised Git repository
            with at least one commit).
        private: Whether the repository should be private.

    Returns:
        The stdout from ``gh repo create``.

    Raises:
        CommandExecutionError: If the ``gh`` command fails.
    """
    visibility = "--private" if private else "--public"
    return await _run_command(
        [
            "gh",
            "repo",
            "create",
            name,
            "--source=.",
            "--remote=origin",
            visibility,
            "--push",
            "--yes",
        ],
        cwd=path,
        description=f"gh repo create {name} ({'private' if private else 'public'})",
    )
