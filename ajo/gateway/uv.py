"""Async gateway for ``uv`` (Astral package manager) operations.

Provides non-blocking wrappers around ``uv init``, ``uv add``, and
``uv run`` so the TUI stays responsive during dependency operations.

Every function has a ``*_streaming`` variant that accepts a
*progress_callback* for live line-by-line output during long-running
operations such as ``uv sync`` or ``uv add django``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from ajo.gateway.utils import _run_command, _run_command_streaming


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


async def uv_add(
    packages: Sequence[str],
    path: Path,
    *,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    """Add one or more PyPI packages to the project (``uv add ...``).

    When *progress_callback* is provided the subprocess output is
    streamed live line-by-line.  Otherwise the function behaves
    identically to the non-streaming original.

    Args:
        packages: Package names to install (e.g. ``["django"]``).
        path: Project directory containing ``pyproject.toml``.
        progress_callback: ``(line_number, line_text)`` called for
            every line of stdout.

    Returns:
        The combined stdout from ``uv add``.

    Raises:
        CommandExecutionError: If ``uv add`` returns a non-zero exit.
    """
    if progress_callback is not None:
        return await _run_command_streaming(
            ["uv", "add", *packages],
            cwd=path,
            description=f"uv add {' '.join(packages)}",
            progress_callback=progress_callback,
        )
    return await _run_command(
        ["uv", "add", *packages],
        cwd=path,
        description=f"uv add {' '.join(packages)}",
    )


async def uv_add_dev(
    packages: Sequence[str],
    path: Path,
    *,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    """Add dev-dependencies (``uv add --dev ...``) with optional streaming.

    Args:
        packages: Dev-dependency package names.
        path: Project directory containing ``pyproject.toml``.
        progress_callback: ``(line_number, line_text)`` called for
            every line of stdout.

    Returns:
        The combined stdout from ``uv add --dev``.
    """
    if progress_callback is not None:
        return await _run_command_streaming(
            ["uv", "add", "--dev", *packages],
            cwd=path,
            description=f"uv add --dev {' '.join(packages)}",
            progress_callback=progress_callback,
        )
    return await _run_command(
        ["uv", "add", "--dev", *packages],
        cwd=path,
        description=f"uv add --dev {' '.join(packages)}",
    )


async def uv_sync(
    path: Path,
    *,
    timeout: int = 120,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    """Lock and sync the project environment (``uv sync``).

    This is the central operation for ``uv sync`` — by far the most
    latency-critical step during scaffolding.  The streaming variant
    keeps the TUI alive by feeding output lines to a progress bar.

    Args:
        path: Project directory with ``pyproject.toml``.
        timeout: Max seconds to wait for ``uv sync``.
        progress_callback: ``(line_number, line_text)`` called for
            every line of stdout.

    Returns:
        The combined stdout from ``uv sync``.
    """
    if progress_callback is not None:
        return await _run_command_streaming(
            ["uv", "sync"],
            cwd=path,
            timeout=timeout,
            description="uv sync",
            progress_callback=progress_callback,
        )
    return await _run_command(
        ["uv", "sync"],
        cwd=path,
        timeout=timeout,
        description="uv sync",
    )


async def uv_run(
    args: Sequence[str],
    path: Path,
    *,
    timeout: int | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    """Run a command inside the ``uv``-managed environment (``uv run ...``).

    Args:
        args: Arguments to pass to ``uv run`` (e.g. ``["python", "manage.py", "check"]``).
        path: Project directory with a ``pyproject.toml`` and ``.venv``.
        timeout: Optional timeout in seconds.
        progress_callback: ``(line_number, line_text)`` called for
            every line of stdout.

    Returns:
        The combined stdout from the command.

    Raises:
        CommandExecutionError: On non-zero exit, timeout, or startup failure.
    """
    if progress_callback is not None:
        return await _run_command_streaming(
            ["uv", "run", *args],
            cwd=path,
            timeout=timeout,
            description=f"uv run {' '.join(args)}",
            progress_callback=progress_callback,
        )
    return await _run_command(
        ["uv", "run", *args],
        cwd=path,
        timeout=timeout,
        description=f"uv run {' '.join(args)}",
    )
