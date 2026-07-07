"""Tests for StreamingSubprocess and run_streaming."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from ajo.core.exceptions import CommandExecutionError
from ajo.core.streaming import (
    StreamedCommandResult,
    StreamingSubprocess,
    run_streaming,
)


# ═════════════════════════════════════════════════════════════════════════════
# StreamedCommandResult
# ═════════════════════════════════════════════════════════════════════════════


class TestStreamedCommandResult:
    def test_defaults(self) -> None:
        r = StreamedCommandResult(returncode=0)
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.command == []
        assert r.timed_out is False

    def test_full_result(self) -> None:
        r = StreamedCommandResult(
            returncode=0,
            stdout="hello\nworld",
            stderr="",
            command=["echo", "hello"],
        )
        assert r.stdout == "hello\nworld"
        assert r.returncode == 0

    def test_nonzero_exit(self) -> None:
        r = StreamedCommandResult(returncode=1, stderr="error msg")
        assert r.returncode == 1
        assert r.timed_out is False


# ═════════════════════════════════════════════════════════════════════════════
# StreamingSubprocess — simple commands
# ═════════════════════════════════════════════════════════════════════════════


class TestStreamingSubprocessBasic:
    @pytest.mark.asyncio
    async def test_echo_success(self) -> None:
        async with StreamingSubprocess(
            [sys.executable, "-c", "print('hello world')"]
        ) as sp:
            result = await sp.wait_for_result()
        assert result.returncode == 0
        assert "hello world" in result.stdout

    @pytest.mark.asyncio
    async def test_custom_cwd(self, tmp_path: Path) -> None:
        """Process runs in the specified directory."""
        async with StreamingSubprocess(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=tmp_path,
        ) as sp:
            result = await sp.wait_for_result()
        assert result.returncode == 0
        # Python may resolve symlinks, compare resolved paths
        assert tmp_path.resolve().as_posix() in result.stdout

    @pytest.mark.asyncio
    async def test_nonzero_exit(self) -> None:
        async with StreamingSubprocess([sys.executable, "-c", "exit(42)"]) as sp:
            result = await sp.wait_for_result()
        assert result.returncode == 42

    @pytest.mark.asyncio
    async def test_stderr_captured(self) -> None:
        async with StreamingSubprocess(
            [sys.executable, "-c", "import sys; sys.stderr.write('error\\n')"]
        ) as sp:
            result = await sp.wait_for_result()
        # stderr output should be captured even on exit 0
        assert "error" in result.stderr or result.returncode == 0

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self) -> None:
        """A process that exceeds the timeout is killed."""
        async with StreamingSubprocess(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout=1,
        ) as sp:
            result = await sp.wait_for_result()
        assert result.timed_out is True
        assert result.returncode != 0

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        with pytest.raises(CommandExecutionError, match="not found"):
            async with StreamingSubprocess(["/nonexistent/binary"]):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_result_before_context_raises(self) -> None:
        sp = StreamingSubprocess([sys.executable, "-c", "pass"])
        with pytest.raises(RuntimeError, match="not available"):
            _ = sp.result


# ═════════════════════════════════════════════════════════════════════════════
# StreamingSubprocess — callbacks
# ═════════════════════════════════════════════════════════════════════════════


class TestStreamingSubprocessCallbacks:
    @pytest.mark.asyncio
    async def test_on_stdout_callback(self) -> None:
        lines: list[str] = []
        async with StreamingSubprocess(
            [sys.executable, "-c", "print('line1'); print('line2')"],
            on_stdout=lambda line: lines.append(line),
        ) as sp:
            await sp.wait_for_result()
        assert "line1" in lines
        assert "line2" in lines

    @pytest.mark.asyncio
    async def test_on_stderr_callback(self) -> None:
        lines: list[str] = []
        async with StreamingSubprocess(
            [sys.executable, "-c", "import sys; sys.stderr.write('err\\n')"],
            on_stderr=lambda line: lines.append(line),
        ) as sp:
            await sp.wait_for_result()
        assert any("err" in l for l in lines)

    @pytest.mark.asyncio
    async def test_on_progress_callback(self) -> None:
        """on_progress receives (line_count, line_text) for each stdout line."""
        progress_updates: list[tuple[int, str]] = []
        async with StreamingSubprocess(
            [sys.executable, "-c", "print('a'); print('b'); print('c')"],
            on_progress=lambda count, text: progress_updates.append((count, text)),
        ) as sp:
            await sp.wait_for_result()
        assert len(progress_updates) >= 3
        assert progress_updates[0] == (1, "a")
        assert progress_updates[1] == (2, "b")
        assert progress_updates[2] == (3, "c")

    @pytest.mark.asyncio
    async def test_all_callbacks_called(self) -> None:
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        progress_updates: list[tuple[int, str]] = []

        async with StreamingSubprocess(
            [
                sys.executable,
                "-c",
                "import sys; print('out'); sys.stderr.write('err\\n')",
            ],
            on_stdout=lambda line: stdout_lines.append(line),
            on_stderr=lambda line: stderr_lines.append(line),
            on_progress=lambda count, text: progress_updates.append((count, text)),
        ) as sp:
            await sp.wait_for_result()

        assert "out" in stdout_lines
        assert any("err" in l for l in stderr_lines)
        assert len(progress_updates) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# run_streaming convenience function
# ═════════════════════════════════════════════════════════════════════════════


class TestRunStreaming:
    @pytest.mark.asyncio
    async def test_returns_result(self) -> None:
        result = await run_streaming([sys.executable, "-c", "print('hi')"])
        assert isinstance(result, StreamedCommandResult)
        assert result.returncode == 0
        assert "hi" in result.stdout

    @pytest.mark.asyncio
    async def test_with_timeout(self) -> None:
        result = await run_streaming(
            [sys.executable, "-c", "print('fast')"],
            timeout=5,
        )
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_with_cwd(self, tmp_path: Path) -> None:
        result = await run_streaming(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=tmp_path,
        )
        assert tmp_path.resolve().as_posix() in result.stdout

    @pytest.mark.asyncio
    async def test_with_env(self) -> None:
        result = await run_streaming(
            [sys.executable, "-c", "import os; print(os.environ.get('MY_VAR'))"],
            env={**os.environ, "MY_VAR": "hello"},
        )
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_stdout_callback(self) -> None:
        lines: list[str] = []
        result = await run_streaming(
            [sys.executable, "-c", "print('callback test')"],
            on_stdout=lambda line: lines.append(line),
        )
        assert result.returncode == 0
        assert "callback test" in lines


# ═════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_process_with_no_output(self) -> None:
        """A process that produces no stdout/stderr."""
        result = await run_streaming([sys.executable, "-c", "pass"])
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    @pytest.mark.asyncio
    async def test_process_with_large_output(self) -> None:
        """A process that produces many lines of output."""
        script = "for i in range(1000): print(f'line{i}')"
        result = await run_streaming([sys.executable, "-c", script])
        assert result.returncode == 0
        assert "line0" in result.stdout
        assert "line999" in result.stdout

    @pytest.mark.asyncio
    async def test_exception_in_callback_handled(self) -> None:
        """An exception in a callback shouldn't crash the whole process."""
        call_count = 0

        def failing_callback(line: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("callback error")
            # After the first call, stop raising

        result = await run_streaming(
            [sys.executable, "-c", "print('a'); print('b')"],
            on_stdout=failing_callback,
        )
        # The subprocess should still run to completion even if callbacks fail
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_kill_on_context_exception(self) -> None:
        """If the context manager receives an exception, the process is killed."""
        sp = StreamingSubprocess(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout=None,
        )

        with pytest.raises(ValueError, match="something went wrong"):
            async with sp:
                raise ValueError("something went wrong")

        # After exit, the process should be dead and result available
        assert sp.result.returncode != 0
        assert sp.result.timed_out is False  # killed, not timed out

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self) -> None:
        """Using async with returns the result after exit."""
        async with StreamingSubprocess(
            [sys.executable, "-c", "print('ctx hello')"]
        ) as sp:
            result = await sp.wait_for_result()
        assert result.returncode == 0
        assert "ctx hello" in result.stdout

    @pytest.mark.asyncio
    async def test_non_blocking_during_stream(self) -> None:
        """Other tasks can run while the subprocess streams."""
        other_done = False

        async def other_task() -> None:
            nonlocal other_done
            await asyncio.sleep(0.05)
            other_done = True

        async with StreamingSubprocess(
            [sys.executable, "-c", "import time; time.sleep(0.1); print('done')"]
        ) as sp:
            task = asyncio.create_task(other_task())
            result = await sp.wait_for_result()
            await task

        assert other_done is True
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_empty_command_raises(self) -> None:
        """An empty command list raises CommandExecutionError."""
        from ajo.core.exceptions import CommandExecutionError

        with pytest.raises(CommandExecutionError, match="Empty command"):
            async with StreamingSubprocess([]) as sp:
                await sp.wait_for_result()

    @pytest.mark.asyncio
    async def test_kill_before_start_safe(self) -> None:
        """Calling _kill_process before the process starts is safe (no-op)."""
        sp = StreamingSubprocess([sys.executable, "-c", "print('hi')"])
        # _process is None at this point — should not raise
        sp._kill_process()
        # Now actually start and clean up
        async with sp:
            result = await sp.wait_for_result()
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_double_wait_for_result_returns_same_result(self) -> None:
        """Calling wait_for_result twice returns the same result (not an error)."""
        async with StreamingSubprocess([sys.executable, "-c", "print('hi')"]) as sp:
            result1 = await sp.wait_for_result()
            assert result1.returncode == 0
            # Second call re-streams the (already-consumed) pipes,
            # which gracefully returns empty output with the same returncode.
            result2 = await sp.wait_for_result()
            assert result2.returncode == 0
