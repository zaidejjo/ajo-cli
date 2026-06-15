"""Async gateway for ``uv`` (Astral package manager) operations.

Provides non-blocking wrappers around ``uv init``, ``uv add``, and
``uv run`` so the TUI stays responsive during dependency operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ajo.gateway.utils import _run_command


async def uv_init(path: Path) -> None:
    """Initialise a ``uv`` project at *path* (``uv init --bare``).

    Args:
        path: Target project directory (must exist).

    Raises:
        CommandExecutionError: If ``uv init`` returns a non-zero exit.
    """
    await _run_command(
        ["uv", "init", "--bare"],
        cwd=path,
        description="uv init --bare",
    )


async def uv_add(packages: Sequence[str], path: Path) -> str:
    """Add one or more PyPI packages to the project (``uv add ...``).

    Args:
        packages: Package names to install (e.g. ``["django"]``).
        path: Project directory containing ``pyproject.toml``.

    Returns:
        The combined stdout from ``uv add``.

    Raises:
        CommandExecutionError: If ``uv add`` returns a non-zero exit.
    """
    return await _run_command(
        ["uv", "add", *packages],
        cwd=path,
        description=f"uv add {' '.join(packages)}",
    )


async def uv_run(args: Sequence[str], path: Path, *, timeout: int | None = None) -> str:
    """Run a command inside the ``uv``-managed environment (``uv run ...``).

    Args:
        args: Arguments to pass to ``uv run`` (e.g. ``["python", "manage.py", "check"]``).
        path: Project directory with a ``pyproject.toml`` and ``.venv``.
        timeout: Optional timeout in seconds.

    Returns:
        The combined stdout from the command.

    Raises:
        CommandExecutionError: If the command returns a non-zero exit,
            or if a timeout occurs.
    """
    return await _run_command(
        ["uv", "run", *args],
        cwd=path,
        timeout=timeout,
        description=f"uv run {' '.join(args)}",
    )
