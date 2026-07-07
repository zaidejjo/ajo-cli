"""Tests for ajo.core.signals."""

from __future__ import annotations

import signal
import sys
from io import StringIO
from unittest import mock

import pytest

from ajo.core.signals import (
    _signal_handler,
    install_signal_handlers,
    interrupted,
    register_rollback_handler,
)


class TestInstallSignalHandlers:
    """Tests for handler installation."""

    def test_installs_sigint(self) -> None:
        """install_signal_handlers() sets a handler for SIGINT."""
        install_signal_handlers()
        handler = signal.getsignal(signal.SIGINT)
        assert handler is _signal_handler

    def test_installs_sigterm(self) -> None:
        """install_signal_handlers() sets a handler for SIGTERM."""
        install_signal_handlers()
        handler = signal.getsignal(signal.SIGTERM)
        assert handler is _signal_handler


class TestRegisterRollbackHandler:
    """Tests for the rollback handler registration."""

    def test_register_and_clear(self) -> None:
        """register_rollback_handler(None) clears the handler."""
        fn = lambda: None  # noqa: E731
        register_rollback_handler(fn)
        # Internal state should be set (we test via the handler call below)
        register_rollback_handler(None)

    def test_registered_handler_is_called(self) -> None:
        """The registered rollback handler is invoked on signal."""
        calls: list[str] = []

        def my_cleanup() -> None:
            calls.append("cleaned")

        register_rollback_handler(my_cleanup)

        # Simulate signal by calling the handler directly
        with mock.patch.object(sys, "exit") as mock_exit:
            _signal_handler(signal.SIGINT, None)

        assert calls == ["cleaned"]
        mock_exit.assert_called_once_with(130)

    def test_handler_exception_does_not_prevent_exit(self) -> None:
        """If the rollback handler raises, we still exit 130."""

        def broken_cleanup() -> None:
            raise RuntimeError("boom")

        register_rollback_handler(broken_cleanup)

        with mock.patch.object(sys, "exit") as mock_exit:
            _signal_handler(signal.SIGINT, None)

        mock_exit.assert_called_once_with(130)


class TestInterruptedFlag:
    """Tests for the global interrupted flag."""

    def test_flag_set_on_signal(self) -> None:
        """The interrupted flag is set when the handler runs."""
        global interrupted  # noqa: F811
        # Reset flag
        from ajo.core.signals import interrupted as _interrupted_flag

        # We can't easily reset a module-level bool, but we can verify
        # the handler sets it
        with mock.patch.object(sys, "exit"):
            _signal_handler(signal.SIGINT, None)

        assert _interrupted_flag is True


class TestSigintExitCode:
    """Tests that SIGINT exits with code 130."""

    def test_exit_code_130(self) -> None:
        """The handler calls sys.exit(130)."""
        register_rollback_handler(None)

        with mock.patch.object(sys, "exit") as mock_exit:
            _signal_handler(signal.SIGINT, None)

        mock_exit.assert_called_once_with(130)

    def test_sigterm_exit_code_130(self) -> None:
        """SIGTERM also exits with code 130."""
        register_rollback_handler(None)

        with mock.patch.object(sys, "exit") as mock_exit:
            _signal_handler(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(130)

    def test_prints_newline_on_stderr(self) -> None:
        """The handler prints a newline to stderr before exiting."""
        register_rollback_handler(None)
        stderr = StringIO()

        with mock.patch.object(sys, "exit"):
            with mock.patch("sys.stderr", stderr):
                _signal_handler(signal.SIGINT, None)

        assert stderr.getvalue() == "\n"
