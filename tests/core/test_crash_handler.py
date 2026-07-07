"""Tests for crash dump handler."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ajo.core.crash_handler import (
    CRASHES_DIR,
    _build_dump_text,
    _redact_env,
    _redact_value,
    _should_redact_env_key,
    crash_excepthook,
    install_crash_handler,
    uninstall_crash_handler,
    write_crash_dump,
)


# ═════════════════════════════════════════════════════════════════════════════
# _redact_value
# ═════════════════════════════════════════════════════════════════════════════


class TestRedactValue:
    def test_short_value_fully_redacted(self) -> None:
        assert _redact_value("abc") == "***"

    def test_long_value_partially_shown(self) -> None:
        result = _redact_value("abcdefghijkl")
        assert result == "ab***kl"

    def test_eight_chars_fully_redacted(self) -> None:
        assert _redact_value("12345678") == "***"

    def test_nine_chars_partially_shown(self) -> None:
        result = _redact_value("123456789")
        assert result == "12***89"


# ═════════════════════════════════════════════════════════════════════════════
# _should_redact_env_key
# ═════════════════════════════════════════════════════════════════════════════


class TestShouldRedactEnvKey:
    def test_api_key_is_sensitive(self) -> None:
        assert _should_redact_env_key("API_KEY") is True

    def test_token_is_sensitive(self) -> None:
        assert _should_redact_env_key("GITHUB_TOKEN") is True

    def test_secret_is_sensitive(self) -> None:
        assert _should_redact_env_key("MY_SECRET") is True

    def test_password_is_sensitive(self) -> None:
        assert _should_redact_env_key("DB_PASSWORD") is True

    def test_auth_is_sensitive(self) -> None:
        assert _should_redact_env_key("HTTP_AUTH") is True

    def test_home_is_not_sensitive(self) -> None:
        assert _should_redact_env_key("HOME") is False

    def test_path_is_not_sensitive(self) -> None:
        assert _should_redact_env_key("PATH") is False


# ═════════════════════════════════════════════════════════════════════════════
# _redact_env
# ═════════════════════════════════════════════════════════════════════════════


class TestRedactEnv:
    def test_redacts_sensitive_keys(self) -> None:
        env = {"HOME": "/home/user", "API_KEY": "sk-abcdef123456", "PATH": "/usr/bin"}
        result = _redact_env(env)
        assert result["HOME"] == "/home/user"
        assert result["API_KEY"] != "sk-abcdef123456"
        assert "***" in result["API_KEY"]
        assert result["PATH"] == "/usr/bin"

    def test_does_not_mutate_original(self) -> None:
        env = {"SECRET": "my-password"}
        original_id = id(env)
        result = _redact_env(env)
        assert id(result) != original_id


# ═════════════════════════════════════════════════════════════════════════════
# _build_dump_text
# ═════════════════════════════════════════════════════════════════════════════


class TestBuildDumpText:
    def test_contains_exception_info(self) -> None:
        try:
            raise ValueError("test crash")
        except ValueError as exc:
            text = _build_dump_text(exc)

        assert "CRASH DUMP" in text
        assert "ValueError" in text
        assert "test crash" in text
        assert "Ajo version" in text

    def test_contains_system_info(self) -> None:
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            text = _build_dump_text(exc)

        assert "Python:" in text
        assert "Platform:" in text

    def test_contains_redacted_env(self) -> None:
        try:
            raise Exception("test")
        except Exception as exc:
            text = _build_dump_text(exc)

        assert "ENVIRONMENT VARIABLES" in text

    def test_contains_traceback(self) -> None:
        try:
            raise ValueError("traceback test")
        except ValueError as exc:
            text = _build_dump_text(exc)

        assert "TRACEBACK" in text
        assert "traceback test" in text


# ═════════════════════════════════════════════════════════════════════════════
# write_crash_dump
# ═════════════════════════════════════════════════════════════════════════════


class TestWriteCrashDump:
    def test_writes_to_crashes_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tmp = Path("/tmp/test-crashes")
        monkeypatch.setattr("ajo.core.crash_handler.CRASHES_DIR", tmp)
        try:
            exc = ValueError("crash test")
            path = write_crash_dump(exc)
            assert path is not None
            assert path.exists()
            assert path.parent == tmp
            content = path.read_text()
            assert "crash test" in content
        finally:
            # Cleanup
            if tmp.exists():
                import shutil

                shutil.rmtree(tmp, ignore_errors=True)

    def test_returns_none_on_permission_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(err: str) -> None:
            raise PermissionError(err)

        monkeypatch.setattr(
            "ajo.core.crash_handler.CRASHES_DIR",
            Path("/nonexistent-parent"),
        )
        # This should not raise
        result = write_crash_dump(ValueError("test"))
        assert result is None

    def test_creates_directory_if_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            crash_dir = Path(tmpdir) / "crashes"
            monkeypatch.setattr("ajo.core.crash_handler.CRASHES_DIR", crash_dir)
            assert not crash_dir.exists()
            result = write_crash_dump(ValueError("dir test"))
            assert result is not None
            assert crash_dir.is_dir()


# ═════════════════════════════════════════════════════════════════════════════
# crash_excepthook
# ═════════════════════════════════════════════════════════════════════════════


class TestCrashExcepthook:
    def test_handles_keyboard_interrupt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KeyboardInterrupt should NOT produce a crash dump."""
        written = []

        def mock_write_crash_dump(exc):
            written.append(exc)
            return None

        monkeypatch.setattr(
            "ajo.core.crash_handler.write_crash_dump", mock_write_crash_dump
        )
        crash_excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        assert len(written) == 0

    def test_handles_system_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SystemExit should NOT produce a crash dump."""
        written = []

        def mock_write_crash_dump(exc):
            written.append(exc)
            return None

        monkeypatch.setattr(
            "ajo.core.crash_handler.write_crash_dump", mock_write_crash_dump
        )
        crash_excepthook(SystemExit, SystemExit(0), None)
        assert len(written) == 0

    def test_writes_dump_for_unhandled_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regular exceptions should produce a crash dump."""
        written = []

        def mock_write_crash_dump(exc):
            written.append(exc)
            return Path("/fake/path")

        monkeypatch.setattr(
            "ajo.core.crash_handler.write_crash_dump", mock_write_crash_dump
        )
        crash_excepthook(ValueError, ValueError("test"), None)
        assert len(written) == 1
        assert isinstance(written[0], ValueError)


# ═════════════════════════════════════════════════════════════════════════════
# install_crash_handler / uninstall_crash_handler
# ═════════════════════════════════════════════════════════════════════════════


class TestInstallCrashHandler:
    def test_install_replaces_excepthook(self) -> None:
        original = sys.excepthook
        try:
            install_crash_handler()
            assert sys.excepthook is not original
        finally:
            uninstall_crash_handler()
            assert sys.excepthook == original

    def test_install_is_idempotent(self) -> None:
        original = sys.excepthook
        try:
            install_crash_handler()
            hook1 = sys.excepthook
            install_crash_handler()  # Second call
            assert sys.excepthook is hook1
        finally:
            uninstall_crash_handler()
            assert sys.excepthook == original


# ═════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_redact_env_empty(self) -> None:
        assert _redact_env({}) == {}

    def test_redact_env_no_sensitive(self) -> None:
        env = {"HOME": "/home/user", "EDITOR": "vim"}
        result = _redact_env(env)
        assert result == env

    def test_build_dump_no_exception_message(self) -> None:
        """An exception with no message should still produce a dump."""
        text = _build_dump_text(ValueError())
        assert "ValueError" in text

    def test_crashes_dir_default_path(self) -> None:
        assert "crashes" in str(CRASHES_DIR)
