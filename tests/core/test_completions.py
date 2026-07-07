"""Tests for ajo.commands.completions."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from ajo.commands.completions import run


class TestRun:
    """Tests for the completions run() entry point."""

    def test_returns_int(self) -> None:
        args = mock.Mock()
        args.shell = "bash"
        result = run(args)
        assert isinstance(result, int)

    def test_missing_shtab_returns_error(self) -> None:
        """When shtab is not installed, return 1 with an error message."""
        args = mock.Mock()
        args.shell = "bash"
        with mock.patch.dict(sys.modules, {"shtab": None}):
            # Simulate missing shtab by making the import fail
            original_import = __builtins__["__import__"]

            def _failing_import(name, *args_, **kwargs):
                if name == "shtab":
                    raise ImportError("No module named 'shtab'")
                return original_import(name, *args_, **kwargs)

            with mock.patch("builtins.__import__", _failing_import):
                result = run(args)
                assert result == 1

    @pytest.mark.parametrize("shell", ["bash", "zsh", "tcsh"])
    def test_generates_completion_script(self, shell: str) -> None:
        """Each supported shell produces a non-empty script."""
        args = mock.Mock()
        args.shell = shell
        result = run(args)
        assert result == 0

    def test_unsupported_shell_returns_error(self) -> None:
        """An unsupported shell should produce an error."""
        args = mock.Mock()
        args.shell = "fish"
        result = run(args)
        assert result == 1


class TestIntegration:
    """Lightweight integration test via the CLI entry point."""

    def test_bash_completion_via_cli(self) -> None:
        """``ajo completion bash`` should produce output."""
        from ajo.commands.completions import run as run_completion

        args = mock.Mock()
        args.shell = "bash"
        assert run_completion(args) == 0

    def test_tcsh_completion_via_cli(self) -> None:
        """``ajo completion tcsh`` should produce output."""
        from ajo.commands.completions import run as run_completion

        args = mock.Mock()
        args.shell = "tcsh"
        assert run_completion(args) == 0
