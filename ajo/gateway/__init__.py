"""Async I/O gateway layer for external subprocess calls.

This package wraps all external-tool interactions (``uv``, ``git``,
``gh``) in clean :mod:`asyncio`-based APIs so the calling code never
blocks the event loop.

Every public function raises :exc:`~ajo.core.exceptions.CommandExecutionError`
on a non-zero exit, carrying the exact command, return code, and captured
``stderr`` for rich error reporting.
"""

from ajo.gateway.uv import uv_add, uv_init, uv_run
from ajo.gateway.git import git_add_all, git_commit, git_init, get_git_branch
from ajo.gateway.gh import (
    gh_check_auth,
    gh_check_installed,
    gh_repo_create,
)

__all__ = [
    # uv
    "uv_init",
    "uv_add",
    "uv_run",
    # git
    "git_init",
    "git_add_all",
    "git_commit",
    "get_git_branch",
    # gh
    "gh_check_installed",
    "gh_check_auth",
    "gh_repo_create",
]
