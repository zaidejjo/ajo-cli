"""Shared utilities for the gateway package.

This module is **internal** — it should not be imported from outside
``ajo/gateway/``.
"""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Sequence

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
    timeout: int | None = None,
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
        timeout: Optional timeout in seconds.  If the process does not
            complete within this window a ``CommandExecutionError`` is
            raised.
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
