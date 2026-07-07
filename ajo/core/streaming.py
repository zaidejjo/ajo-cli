"""Advanced async subprocess manager with line-level progress streaming.

Provides the :class:`StreamingSubprocess` context manager that wraps
:func:`asyncio.create_subprocess_exec` and delivers stdout/stderr lines
to caller-provided callbacks in real time — all within the event loop
(no threads, no ``asyncio.to_thread``).

Usage::

    async with StreamingSubprocess(
        ["uv", "sync"],
        cwd=project_path,
        on_stdout=lambda line: logger.info("uv: %s", line),
        on_stderr=lambda line: logger.warning("uv: %s", line),
        on_progress=lambda lines, text: progress.update(task, advance=1),
    ) as result:
        ...

    print(f"Exit: {result.returncode}")
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ajo.core.exceptions import CommandExecutionError

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class StreamedCommandResult:
    """Result of a completed streaming subprocess.

    Attributes:
        returncode: Process exit code (``0`` for success).
        stdout: Full captured stdout text.
        stderr: Full captured stderr text.
        command: The command that was executed.
        timed_out: ``True`` if the process was killed due to timeout.
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""
    command: list[str] = field(default_factory=list)
    timed_out: bool = False


# ── Streaming subprocess ──────────────────────────────────────────────────────


class StreamingSubprocess:
    """Async context manager that runs a subprocess with live streaming.

    Every line written to stdout or stderr is forwarded to the
    corresponding callback.  An optional *on_progress* callback is
    invoked after each stdout line to support progress-bar advancement.

    The subprocess is created via ``asyncio.create_subprocess_exec``
    (never ``shell=True``).  Timeout is enforced via
    ``asyncio.wait_for`` and the process is killed on timeout.
    """

    def __init__(
        self,
        command: list[str],
        *,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> None:
        """Initialise the streaming subprocess.

        Args:
            command: Command and arguments (e.g. ``["uv", "sync"]``).
            cwd: Working directory for the process.
            env: Environment variables (inherits current process by default).
            timeout: Max seconds to wait for completion.
            on_stdout: Called for each line of stdout (without newline).
            on_stderr: Called for each line of stderr (without newline).
            on_progress: ``(line_count, line_text)`` called after each
                stdout line for progress-bar advancement.
        """
        self._command = list(command)
        self._cwd = Path(cwd) if cwd else None
        self._env = env
        self._timeout = timeout
        self._on_stdout = on_stdout
        self._on_stderr = on_stderr
        self._on_progress = on_progress

        self._process: asyncio.subprocess.Process | None = None
        self._result: StreamedCommandResult | None = None
        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._line_count: int = 0

    # ── Context manager protocol ─────────────────────────────────────────

    async def __aenter__(self) -> StreamingSubprocess:
        """Start the subprocess and begin streaming."""
        if not self._command:
            raise CommandExecutionError(
                message="Empty command provided to StreamingSubprocess",
                command=self._command,
                return_code=None,
                stderr="The command list is empty — nothing to execute.",
            )
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                cwd=self._cwd,
                env=self._env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise CommandExecutionError(
                message=f"Executable not found: {self._command[0]}",
                command=self._command,
                return_code=None,
                stderr=f"The program {self._command[0]!r} is not installed or not on PATH.",
            )
        except PermissionError:
            raise CommandExecutionError(
                message=f"Permission denied: {self._command[0]}",
                command=self._command,
                return_code=None,
                stderr=f"Permission denied: {self._command[0]} is not executable.",
            )

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool | None:
        """Wait for the process to finish and build the result.

        If the context exits due to an exception (including timeout),
        the process is killed first.
        """
        if self._process is None:
            return None

        timed_out = False

        if exc_type is not None:
            # Kill process on any context-manager exception
            self._kill_process()

        try:
            assert self._process.stdout is not None
            assert self._process.stderr is not None

            # Read remaining data from both streams concurrently
            await asyncio.gather(
                self._read_remaining(self._process.stdout, self._stdout_lines, True),
                self._read_remaining(self._process.stderr, self._stderr_lines, False),
            )
            await self._process.wait()
        except Exception:
            self._kill_process()
            await self._process.wait()

        returncode = self._process.returncode or 0

        self._result = StreamedCommandResult(
            returncode=returncode,
            stdout="".join(self._stdout_lines).strip(),
            stderr="".join(self._stderr_lines).strip(),
            command=self._command,
            timed_out=timed_out,
        )

        return None  # Don't suppress exceptions

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def result(self) -> StreamedCommandResult:
        """Result after the context exits.

        Raises:
            RuntimeError: If accessed before the context exits.
        """
        if self._result is None:
            raise RuntimeError(
                "StreamedCommandResult is not available until the "
                "context manager exits."
            )
        return self._result

    async def wait_for_result(
        self,
        timeout: int | None = None,
    ) -> StreamedCommandResult:
        """Wait for the process to complete and return the result.

        This is an alternative to the context-manager protocol when
        the caller does not need to manage the lifetime explicitly
        but still wants streaming callbacks.

        Args:
            timeout: Override the instance-level timeout for this call.

        Returns:
            A :class:`StreamedCommandResult`.

        Raises:
            CommandExecutionError: If the process times out.
        """
        effective_timeout = timeout if timeout is not None else self._timeout

        try:
            await asyncio.wait_for(
                self._stream(),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            self._kill_process()
            if self._process:
                await self._process.wait()

            stdout = "".join(self._stdout_lines).strip()
            stderr = "".join(self._stderr_lines).strip()
            self._result = StreamedCommandResult(
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                command=self._command,
                timed_out=True,
            )

        return self._result

    # ── Internal ─────────────────────────────────────────────────────────

    async def _stream(self) -> None:
        """Read stdout and stderr concurrently until both close."""
        assert self._process is not None
        assert self._process.stdout is not None
        assert self._process.stderr is not None

        await asyncio.gather(
            self._read_stream(self._process.stdout, self._stdout_lines, True),
            self._read_stream(self._process.stderr, self._stderr_lines, False),
        )

        await self._process.wait()

        returncode = self._process.returncode or 0
        self._result = StreamedCommandResult(
            returncode=returncode,
            stdout="".join(self._stdout_lines).strip(),
            stderr="".join(self._stderr_lines).strip(),
            command=self._command,
        )

    async def _read_stream(
        self,
        stream: asyncio.StreamReader,
        target: list[str],
        is_stdout: bool,
    ) -> None:
        """Read lines from a stream until EOF, firing callbacks."""
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace")
            # Strip trailing newline for callbacks
            display_line = line.rstrip("\n\r")
            target.append(line)  # Keep original line for full output

            if is_stdout:
                self._line_count += 1
                try:
                    if self._on_stdout:
                        self._on_stdout(display_line)
                except Exception as cb_exc:
                    logger.warning("stdout callback error: %s", cb_exc)
                try:
                    if self._on_progress:
                        self._on_progress(self._line_count, display_line)
                except Exception as cb_exc:
                    logger.warning("progress callback error: %s", cb_exc)
            else:
                try:
                    if self._on_stderr:
                        self._on_stderr(display_line)
                except Exception as cb_exc:
                    logger.warning("stderr callback error: %s", cb_exc)

    async def _read_remaining(
        self,
        stream: asyncio.StreamReader,
        target: list[str],
        is_stdout: bool,
    ) -> None:
        """Read any remaining data from a stream (non-blocking)."""
        try:
            while True:
                line_bytes = await asyncio.wait_for(stream.readline(), timeout=1.0)
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                target.append(line)
                if is_stdout and self._on_progress:
                    display_line = line.rstrip("\n\r")
                    self._line_count += 1
                    self._on_progress(self._line_count, display_line)
        except (asyncio.TimeoutError, Exception):
            pass

    def _kill_process(self) -> None:
        """Kill the subprocess and wait for termination."""
        if self._process is not None and self._process.returncode is None:
            try:
                self._process.kill()
            except ProcessLookupError:
                pass  # Already dead


# ── Convenience function ──────────────────────────────────────────────────────


async def run_streaming(
    command: list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> StreamedCommandResult:
    """Convenience function: create, stream, and return result.

    This is a shorthand for the context-manager protocol::

        result = await run_streaming(["uv", "sync"], on_progress=...)

    Args:
        command: Command and arguments.
        cwd: Working directory.
        env: Environment overrides.
        timeout: Max seconds to wait.
        on_stdout: Called for each stdout line.
        on_stderr: Called for each stderr line.
        on_progress: ``(line_count, line_text)`` called after each
            stdout line.

    Returns:
        A :class:`StreamedCommandResult`.
    """
    runner = StreamingSubprocess(
        command,
        cwd=cwd,
        env=env,
        timeout=timeout,
        on_stdout=on_stdout,
        on_stderr=on_stderr,
        on_progress=on_progress,
    )
    async with runner:
        result = await runner.wait_for_result()
    return result


__all__ = [
    "StreamedCommandResult",
    "StreamingSubprocess",
    "run_streaming",
]
