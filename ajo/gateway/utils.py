"""Shared utilities for the gateway package.

This module is **internal** — it should not be imported from outside
``ajo/gateway/``.
"""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Callable, Sequence

from ajo.core.exceptions import CommandExecutionError


def _sanitize_command(command: Sequence[str]) -> list[str]:
    """Validate and normalise a command sequence.

    * Ensures every element is a non-empty string.
    * Rejects shell metacharacters that would be dangerous even though
      we never pass ``shell=True``.

    Args:
        command: The raw command sequence (e.g. ``["uv", "init", "--bare"]``).

    Returns:
        The same list, validated.

    Raises:
        ValueError: If any element is empty or contains dangerous characters.
    """
    dangerous = {"|", ";", "&", "$", "`", "(", ")", "{", "}", "<", ">", "!", "#", "~"}
    cleaned: list[str] = []
    for i, part in enumerate(command):
        if not part or not part.strip():
            raise ValueError(f"Command element at index {i} is empty")
        for char in part:
            if char in dangerous:
                raise ValueError(
                    f"Command element at index {i} contains dangerous "
                    f"character {shlex.quote(char)!r}"
                )
        cleaned.append(part)
    return cleaned


async def _run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = 30,
    description: str = "",
) -> str:
    """Execute an external process asynchronously and return its stdout.

    This is the single point of execution for all gateway modules.
    It uses :func:`asyncio.create_subprocess_exec` (never ``shell=True``)
    and raises :exc:`~ajo.core.exceptions.CommandExecutionError` on
    failure.

    Args:
        command: The command and its arguments as a sequence of strings.
        cwd: Working directory for the process (``None`` = inherit from
            the parent process).
        timeout: Timeout in seconds (default ``30``).  If the process does
            not complete within this window a ``CommandExecutionError`` is
            raised.  Pass ``None`` to disable the timeout.
        description: Human-readable label for error messages (e.g.
            ``"uv add django"``).

    Returns:
        The stripped stdout string.

    Raises:
        CommandExecutionError: If the process returns a non-zero exit
            code, times out, or cannot be started.
    """
    safe_command = _sanitize_command(command)

    try:
        process = await asyncio.create_subprocess_exec(
            *safe_command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise CommandExecutionError(
            message=f"Executable not found: {safe_command[0]}",
            command=list(safe_command),
            return_code=None,
            stderr=f"The program {safe_command[0]!r} is not installed or not on PATH.",
        )
    except PermissionError:
        raise CommandExecutionError(
            message=f"Permission denied: {safe_command[0]}",
            command=list(safe_command),
            return_code=None,
            stderr=f"The program {safe_command[0]!r} is not executable.",
        )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()  # avoid zombies
        raise CommandExecutionError(
            message=f"Command timed out after {timeout}s: {description or ' '.join(safe_command)}",
            command=list(safe_command),
            return_code=None,
            stderr=f"Timed out after {timeout} seconds.",
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        raise CommandExecutionError(
            message=(
                f"Command failed with exit code {process.returncode}"
                f"{': ' + description if description else ''}"
            ),
            command=list(safe_command),
            return_code=process.returncode,
            stderr=stderr,
        )

    return stdout


async def _run_command_streaming(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = 30,
    description: str = "",
    progress_callback: Callable[[int, str], None] | None = None,
    total_lines: int = 100,
) -> str:
    """Execute a process asynchronously and stream output line-by-line.

    This variant is identical to :func:`_run_command` but accepts a
    *progress_callback* that is invoked for every line of stdout so that
    callers can update a progress bar or live display.

    Args:
        command: The command and its arguments as a sequence of strings.
        cwd: Working directory for the process.
        timeout: Timeout in seconds (default ``30``).  Pass ``None`` to
            disable the timeout.
        description: Human-readable label for error messages.
        progress_callback: ``(line_number, line_text)`` called for each
            stdout line.
        total_lines: Estimated total lines (used for progress completion).

    Returns:
        The stripped combined stdout string.

    Raises:
        CommandExecutionError: On non-zero exit, timeout, or startup failure.
    """
    safe_command = _sanitize_command(command)

    try:
        process = await asyncio.create_subprocess_exec(
            *safe_command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise CommandExecutionError(
            message=f"Executable not found: {safe_command[0]}",
            command=list(safe_command),
            return_code=None,
            stderr=f"The program {safe_command[0]!r} is not installed or not on PATH.",
        )
    except PermissionError:
        raise CommandExecutionError(
            message=f"Permission denied: {safe_command[0]}",
            command=list(safe_command),
            return_code=None,
            stderr=f"The program {safe_command[0]!r} is not executable.",
        )

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    line_count = 0

    async def _read_stream(
        stream: asyncio.StreamReader,
        target: list[str],
        is_stdout: bool,
    ) -> None:
        nonlocal line_count
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace")
            target.append(line)
            if is_stdout:
                line_count += 1
                if progress_callback:
                    progress_callback(line_count, line.rstrip())

    assert process.stdout is not None
    assert process.stderr is not None
    try:
        await asyncio.wait_for(
            asyncio.gather(
                _read_stream(process.stdout, stdout_parts, True),
                _read_stream(process.stderr, stderr_parts, False),
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise CommandExecutionError(
            message=f"Command timed out after {timeout}s: {description or ' '.join(safe_command)}",
            command=list(safe_command),
            return_code=None,
            stderr=f"Timed out after {timeout} seconds.",
        )

    await process.wait()
    stdout = "".join(stdout_parts).strip()
    stderr = "".join(stderr_parts).strip()

    if process.returncode != 0:
        raise CommandExecutionError(
            message=(
                f"Command failed with exit code {process.returncode}"
                f"{': ' + description if description else ''}"
            ),
            command=list(safe_command),
            return_code=process.returncode,
            stderr=stderr,
        )

    return stdout
