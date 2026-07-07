"""Tests for ajo.gateway.utils — default timeouts and command execution."""

from __future__ import annotations

import asyncio
from inspect import signature
from unittest import mock

import pytest

from ajo.core.exceptions import CommandExecutionError
from ajo.gateway.utils import _run_command, _run_command_streaming, _sanitize_command


class TestSanitizeCommand:
    """Tests for command sanitisation."""

    def test_valid_command(self) -> None:
        assert _sanitize_command(["uv", "add", "django"]) == ["uv", "add", "django"]

    def test_empty_element_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _sanitize_command(["uv", ""])

    def test_dangerous_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="dangerous"):
            _sanitize_command(["uv", "add", "django; rm -rf /"])

    def test_shell_pipe_raises(self) -> None:
        with pytest.raises(ValueError, match="dangerous"):
            _sanitize_command(["uv", "run", "|", "cat"])


class TestRunCommandDefaultTimeout:
    """Tests that _run_command has a sensible default timeout."""

    @pytest.mark.asyncio
    async def test_default_timeout_is_30(self) -> None:
        """The default timeout should be 30 seconds."""
        from inspect import signature

        sig = signature(_run_command)
        param = sig.parameters["timeout"]
        assert param.default == 30

    @pytest.mark.asyncio
    async def test_accepts_none_timeout(self) -> None:
        """Passing None should disable the timeout."""
        sig = signature(_run_command)
        param = sig.parameters["timeout"]
        # Ensure the type annotation allows None
        assert "None" in str(param.annotation)

    @pytest.mark.asyncio
    async def test_timeout_raises_command_execution_error(self) -> None:
        """A command that times out should raise CommandExecutionError."""
        # Simulate a long-running command that exceeds the timeout
        with mock.patch(
            "ajo.gateway.utils.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(CommandExecutionError) as excinfo:
                await _run_command(["sleep", "10"], timeout=1)
            assert "timed out" in str(excinfo.value).lower()


class TestRunCommandStreamingDefaultTimeout:
    """Tests that _run_command_streaming has a sensible default timeout."""

    @pytest.mark.asyncio
    async def test_default_timeout_is_30(self) -> None:
        """The default timeout should be 30 seconds."""
        from inspect import signature

        sig = signature(_run_command_streaming)
        param = sig.parameters["timeout"]
        assert param.default == 30

    @pytest.mark.asyncio
    async def test_accepts_none_timeout(self) -> None:
        """Passing None should disable the timeout."""
        sig = signature(_run_command_streaming)
        param = sig.parameters["timeout"]
        assert "None" in str(param.annotation)

    @pytest.mark.asyncio
    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    async def test_streaming_timeout_raises_command_execution_error(self) -> None:
        """A streaming command that times out should raise CommandExecutionError."""
        with mock.patch(
            "ajo.gateway.utils.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(CommandExecutionError) as excinfo:
                await _run_command_streaming(
                    ["sleep", "10"],
                    timeout=1,
                    progress_callback=lambda line, text: None,
                )
            assert "timed out" in str(excinfo.value).lower()


class TestRunCommandExecution:
    """Tests for actual command execution."""

    @pytest.mark.asyncio
    async def test_successful_command_returns_stdout(self) -> None:
        """A simple echo command should return its output."""
        result = await _run_command(["echo", "hello"], timeout=5)
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_command_not_found_raises_error(self) -> None:
        """A non-existent command should raise CommandExecutionError."""
        with pytest.raises(CommandExecutionError) as excinfo:
            await _run_command(["nonexistent_cmd_xyz"], timeout=5)
        assert "not found" in str(excinfo.value).lower() or "Found" in str(
            excinfo.value
        )

    @pytest.mark.asyncio
    async def test_non_zero_exit_raises_error(self) -> None:
        """A command that fails should raise CommandExecutionError."""
        # Use a simple non-zero exit that doesn't trigger sanitizer
        with pytest.raises(CommandExecutionError) as excinfo:
            await _run_command(["bash", "-c", "exit 1"], timeout=5)
        assert "exit code 1" in str(excinfo.value).lower() or "exit code" in str(
            excinfo.value
        )


class TestGatewayIntegration:
    """Lightweight integration tests for gateway modules."""

    @pytest.mark.asyncio
    async def test_git_init_with_timeout(self) -> None:
        """git_init should work with our default timeout."""
        from ajo.gateway.git import git_init

        # Run in a temp directory
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_repo"
            path.mkdir()
            # Should succeed without timeout error
            await git_init(path)

    @pytest.mark.asyncio
    async def test_uv_init_with_timeout(self) -> None:
        """uv_init should work with our default timeout."""
        from ajo.gateway.uv import uv_init

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_uv_project"
            path.mkdir()
            await uv_init(path)
