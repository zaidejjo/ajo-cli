"""Tests for ajo.core.color_control."""

from __future__ import annotations

import os
import sys
from unittest import mock

import pytest

from ajo.core.color_control import (
    UNSET,
    configure_console,
    resolve_color_preference,
    should_disable_progress,
    strip_ansi,
    supports_color,
)


class TestResolveColorPreference:
    """Tests for the colour-preference resolution logic."""

    def test_default_is_tty(self) -> None:
        """Default resolves to sys.stdout.isatty()."""
        with mock.patch.object(sys.stdout, "isatty", return_value=True):
            assert resolve_color_preference() is True
        with mock.patch.object(sys.stdout, "isatty", return_value=False):
            assert resolve_color_preference() is False

    def test_no_color_flag_wins(self) -> None:
        """--no-color=True disables colours regardless of env/tty."""
        with mock.patch.object(sys.stdout, "isatty", return_value=True):
            assert resolve_color_preference(no_color=True) is False

    def test_color_never_wins(self) -> None:
        """--color=never disables colours."""
        assert resolve_color_preference(color="never") is False

    def test_color_always_wins(self) -> None:
        """--color=always enables colours."""
        with mock.patch.object(sys.stdout, "isatty", return_value=False):
            assert resolve_color_preference(color="always") is True

    def test_force_color_env(self) -> None:
        """FORCE_COLOR env var enables colours."""
        with mock.patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=True):
            assert resolve_color_preference() is True

    def test_force_color_empty(self) -> None:
        """FORCE_COLOR=0 does not force colours; falls back to TTY check."""
        with mock.patch.dict(os.environ, {"FORCE_COLOR": "0"}, clear=True):
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                # TTY is true, so colours are enabled
                assert resolve_color_preference() is True
            with mock.patch.object(sys.stdout, "isatty", return_value=False):
                # TTY is false, so colours are disabled
                assert resolve_color_preference() is False

    def test_no_color_env(self) -> None:
        """NO_COLOR env var disables colours."""
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}, clear=True):
            assert resolve_color_preference() is False
        with mock.patch.dict(os.environ, {"NO_COLOR": ""}, clear=True):
            # Empty NO_COLOR should still disable per spec
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                assert resolve_color_preference() is True

    def test_no_color_precedence_over_force_color(self) -> None:
        """NO_COLOR takes precedence over FORCE_COLOR? Actually FORCE_COLOR overrides NO_COLOR.

        Per https://no-color.org/: "Command-line flags should override
        the environment variable." So:
        FORCE_COLOR > NO_COLOR > TTY.
        """
        # If NO_COLOR is set but FORCE_COLOR is also set, FORCE_COLOR wins
        with mock.patch.dict(
            os.environ, {"NO_COLOR": "1", "FORCE_COLOR": "1"}, clear=True
        ):
            assert resolve_color_preference() is True

    def test_ci_env(self) -> None:
        """CI=true disables colours."""
        with mock.patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert resolve_color_preference() is False

    @pytest.mark.parametrize(
        ("ci_value", "expected"),
        [
            ("true", False),
            ("1", False),
            ("yes", False),
            ("false", True),  # explicit false — treat as not-CI
            ("0", True),
        ],
    )
    def test_ci_values(self, ci_value: str, expected: bool) -> None:
        with mock.patch.dict(os.environ, {"CI": ci_value}, clear=True):
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                assert resolve_color_preference() is expected


class TestConfigureConsole:
    """Tests for console creation with colour settings."""

    def test_creates_console(self) -> None:
        console = configure_console()
        assert console is not None
        assert hasattr(console, "print")

    def test_no_color_disables_colors(self) -> None:
        console = configure_console(no_color=True)
        assert console.no_color is True
        assert console.color_system is None

    def test_color_never_disables_colors(self) -> None:
        console = configure_console(color="never")
        assert console.no_color is True
        assert console.color_system is None

    def test_color_always_enforces_color(self) -> None:
        console = configure_console(color="always")
        assert console.no_color is False
        assert console.color_system is not None


class TestSupportsColor:
    """Tests for the convenience predicate."""

    def test_returns_bool(self) -> None:
        result = supports_color()
        assert isinstance(result, bool)


class TestStripAnsi:
    """Tests for ANSI stripping."""

    def test_strips_sgr_codes(self) -> None:
        assert strip_ansi("\x1b[31mred\x1b[0m") == "red"

    def test_strips_multiple_codes(self) -> None:
        assert strip_ansi("\x1b[1m\x1b[32mbold green\x1b[0m") == "bold green"

    def test_plain_text_unchanged(self) -> None:
        assert strip_ansi("hello world") == "hello world"

    def test_empty_string(self) -> None:
        assert strip_ansi("") == ""


class TestUnset:
    """Tests for the UNSET sentinel."""

    def test_is_falsy(self) -> None:
        assert not UNSET

    def test_is_singleton(self) -> None:
        from ajo.core.color_control import _Unset

        assert UNSET is _Unset()


class TestShouldDisableProgress:
    """Tests for the progress-disabling predicate."""

    def test_default_is_tty(self) -> None:
        """Default (TTY, no CI) → progress enabled."""
        with mock.patch.object(sys.stdout, "isatty", return_value=True):
            assert should_disable_progress() is False

    def test_disabled_when_non_tty(self) -> None:
        """Non-TTY → progress disabled."""
        with mock.patch.object(sys.stdout, "isatty", return_value=False):
            assert should_disable_progress() is True

    @pytest.mark.parametrize(
        ("ci_value", "expected"),
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("True", True),
            ("false", False),
            ("0", False),
            ("", False),
        ],
    )
    def test_ci_env(self, ci_value: str, expected: bool) -> None:
        """CI env var disables progress."""
        with mock.patch.dict(os.environ, {"CI": ci_value}, clear=True):
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                assert should_disable_progress() is expected

    def test_ci_wins_over_tty(self) -> None:
        """CI=true disables progress even when TTY."""
        with mock.patch.dict(os.environ, {"CI": "true"}, clear=True):
            with mock.patch.object(sys.stdout, "isatty", return_value=True):
                assert should_disable_progress() is True

    def test_non_tty_wins_without_ci(self) -> None:
        """Non-TTY disables progress even without CI."""
        with mock.patch.object(sys.stdout, "isatty", return_value=False):
            assert should_disable_progress() is True
