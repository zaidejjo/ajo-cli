"""Async gateway for ``git`` operations.

Provides non-blocking wrappers around common Git commands used during
project scaffolding, plus a fast filesystem-based branch reader that
avoids spawning a subprocess altogether.
"""

from __future__ import annotations

from pathlib import Path

from ajo.gateway.utils import _run_command


async def git_init(path: Path) -> None:
    """Initialise a Git repository at *path* (``git init``).

    Args:
        path: Target directory.

    Raises:
        CommandExecutionError: If ``git init`` fails.
    """
    await _run_command(
        ["git", "init"],
        cwd=path,
        description="git init",
    )


async def git_add_all(path: Path) -> None:
    """Stage all changes (``git add .``).

    Args:
        path: Repository root.

    Raises:
        CommandExecutionError: If ``git add`` fails.
    """
    await _run_command(
        ["git", "add", "."],
        cwd=path,
        description="git add .",
    )


async def git_commit(message: str, path: Path) -> None:
    """Create a commit (``git commit -m <message>``).

    Args:
        message: Commit message.
        path: Repository root.

    Raises:
        CommandExecutionError: If ``git commit`` fails.
    """
    await _run_command(
        ["git", "commit", "-m", message],
        cwd=path,
        description=f'git commit -m "{message}"',
    )


def get_git_branch(project_path: Path) -> str:
    """Read the current Git branch name from ``.git/HEAD``.

    This is a **zero-subprocess** alternative to ``git branch --show-current``
    that reads the filesystem directly, making it practically instant.

    Returns:
        The branch name, or ``"N/A"`` if the path is not a Git repository
        or the HEAD is in detached state (returns the short commit hash).
    """
    head_file = project_path / ".git" / "HEAD"
    if not head_file.exists():
        return "N/A"
    try:
        content = head_file.read_text(encoding="utf-8", errors="replace").strip()
        # Typical content: "ref: refs/heads/main"
        if content.startswith("ref: "):
            return content.removeprefix("ref: refs/heads/")
        # Detached HEAD — return short commit hash
        return content[:7]
    except Exception:
        return "N/A"
