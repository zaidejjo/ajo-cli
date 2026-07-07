"""Tests for ajo.commands.report.

Covers data gathering, secret redaction, output formatting, and the
run() entry point — all with mocked filesystem / subprocess / import
so no real Django project or PyPI is needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from ajo import __version__ as ajo_version
from ajo.commands.report import (
    SENSITIVE_KEY_PATTERNS,
    _copy_to_clipboard,
    _detect_color_depth,
    _format_markdown,
    _gather_ajo_info,
    _gather_config,
    _gather_django_info,
    _gather_python_info,
    _gather_report_data,
    _gather_system_info,
    _gather_terminal_info,
    _gather_update_info,
    _print_report,
    _redact_sensitive_values,
    _write_json,
    _write_markdown,
    run,
)


# ═════════════════════════════════════════════════════════════════════════════
# Data gathering — smoke tests (no mocking needed for static info)
# ═════════════════════════════════════════════════════════════════════════════


class TestGatherSystemInfo:
    def test_returns_expected_keys(self) -> None:
        info = _gather_system_info()
        assert "os" in info
        assert "os_release" in info
        assert "machine" in info


class TestGatherPythonInfo:
    def test_returns_expected_keys(self) -> None:
        info = _gather_python_info()
        assert "version" in info
        assert "executable" in info
        assert info["executable"] == sys.executable


class TestGatherAjoInfo:
    def test_returns_version(self) -> None:
        info = _gather_ajo_info()
        assert info["version"] == ajo_version
        assert "install_path" in info
        assert "environment" in info


class TestGatherTerminalInfo:
    def test_returns_expected_keys(self) -> None:
        info = _gather_terminal_info()
        assert "term_env" in info
        assert "color_term_env" in info
        assert "is_tty" in info
        assert "color_depth" in info
        assert "nerd_font_detected" in info or info["nerd_font_detected"] is None


# ═════════════════════════════════════════════════════════════════════════════
# _detect_color_depth
# ═════════════════════════════════════════════════════════════════════════════


class TestDetectColorDepth:
    def test_truecolor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COLORTERM", "truecolor")
        with patch.object(sys.stdout, "isatty", return_value=True):
            assert _detect_color_depth() == "truecolor"

    def test_256(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch.object(sys.stdout, "isatty", return_value=True):
            assert _detect_color_depth() == "256"

    def test_16(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TERM", "xterm-color")
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch.object(sys.stdout, "isatty", return_value=True):
            assert _detect_color_depth() == "16"

    def test_piped(self) -> None:
        """When not a TTY, piped is reported."""
        with patch.object(sys.stdout, "isatty", return_value=False):
            assert _detect_color_depth() == "none (piped)"

    def test_xterm_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset COLORTERM + bare xterm → 256."""
        monkeypatch.setenv("TERM", "xterm")
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch.object(sys.stdout, "isatty", return_value=True):
            assert _detect_color_depth() == "256"

    def test_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No hints at all → unknown."""
        monkeypatch.delenv("TERM", raising=False)
        monkeypatch.delenv("COLORTERM", raising=False)
        with patch.object(sys.stdout, "isatty", return_value=True):
            assert _detect_color_depth() == "unknown"


# ═════════════════════════════════════════════════════════════════════════════
# _redact_sensitive_values
# ═════════════════════════════════════════════════════════════════════════════


class TestRedactSensitiveValues:
    def test_redacts_secret(self) -> None:
        result = _redact_sensitive_values({"api_key": "sk-12345"})
        assert result["api_key"] == "***REDACTED***"

    def test_redacts_token(self) -> None:
        result = _redact_sensitive_values({"github_token": "ghp_fake"})
        assert result["github_token"] == "***REDACTED***"

    def test_redacts_password(self) -> None:
        result = _redact_sensitive_values({"db_password": "s3cret"})
        assert result["db_password"] == "***REDACTED***"

    def test_redacts_auth(self) -> None:
        result = _redact_sensitive_values({"authorization": "Bearer xyz"})
        assert result["authorization"] == "***REDACTED***"

    def test_preserves_safe_keys(self) -> None:
        """Keys that don't match any sensitive pattern are kept intact."""
        result = _redact_sensitive_values({"nerd_fonts": True, "theme": "cyberpunk"})
        assert result["nerd_fonts"] is True
        assert result["theme"] == "cyberpunk"

    def test_preserves_safe_key_with_substring(self) -> None:
        """A key like 'donation' contains 'tion' not any sensitive pattern."""
        result = _redact_sensitive_values({"donation": "charity"})
        assert result["donation"] == "charity"

    def test_redacts_nested_dict(self) -> None:
        data = {"nested": {"api_key": "sk-123", "name": "hello"}}
        result = _redact_sensitive_values(data)
        assert result["nested"]["api_key"] == "***REDACTED***"
        assert result["nested"]["name"] == "hello"

    def test_case_insensitive(self) -> None:
        result = _redact_sensitive_values({"API_KEY": "sk-12345"})
        assert result["API_KEY"] == "***REDACTED***"


# ═════════════════════════════════════════════════════════════════════════════
# _gather_config
# ═════════════════════════════════════════════════════════════════════════════


class TestGatherConfig:
    def test_redacts_sensitive_values(self) -> None:
        """Verify that sensitive config keys are redacted in the report."""
        fake_data = {
            "nerd_fonts": True,
            "theme": "cyberpunk",
            "api_key": "should-be-hidden",
            "github_token": "should-be-hidden-too",
        }

        with (
            patch("ajo.core.config.CONFIG_FILE") as mock_cfg_file,
            patch("ajo.core.config.ConfigManager") as mock_mgr,
        ):
            mock_cfg_file.is_file.return_value = True
            mock_cfg_file.__str__.return_value = "/fake/config.json"
            instance = mock_mgr.return_value
            instance._data = fake_data

            result = _gather_config()

        assert result is not None
        assert result["nerd_fonts"] is True
        assert result["api_key"] == "***REDACTED***"
        assert result["github_token"] == "***REDACTED***"

    def test_returns_none_on_error(self) -> None:
        with patch("ajo.core.config.ConfigManager", side_effect=Exception):
            result = _gather_config()
            assert result is None


# ═════════════════════════════════════════════════════════════════════════════
# _gather_django_info
# ═════════════════════════════════════════════════════════════════════════════


class TestGatherDjangoInfo:
    def test_returns_dict_when_django(self) -> None:
        """When scan detects a Django project, info is returned."""
        scan_data = {
            "is_django_project": True,
            "project_name": "myproject",
            "django_version": "5.1.3",
            "models_count": 5,
            "apps_count": 2,
            "apps": ["auth", "polls"],
            "middleware_count": 3,
            "url_patterns_count": 4,
        }
        with patch("ajo.commands.scan._gather_scan_data", return_value=scan_data):
            result = _gather_django_info()

        assert result is not None
        assert result["project_name"] == "myproject"
        assert result["django_version"] == "5.1.3"

    def test_returns_none_when_not_django(self) -> None:
        with patch(
            "ajo.commands.scan._gather_scan_data",
            return_value={"is_django_project": False},
        ):
            result = _gather_django_info()
            assert result is None


# ═════════════════════════════════════════════════════════════════════════════
# _gather_update_info
# ═════════════════════════════════════════════════════════════════════════════


class TestGatherUpdateInfo:
    def test_returns_dict_when_cached(self) -> None:
        with patch("ajo.core.updater.get_cached_update") as mock_get:
            mock_get.return_value = ("9.9.9", True)
            result = _gather_update_info()

        assert result is not None
        assert result["latest_version"] == "9.9.9"
        assert result["update_available"] is True

    def test_returns_none_when_no_cache(self) -> None:
        with patch("ajo.core.updater.get_cached_update", return_value=None):
            result = _gather_update_info()
            assert result is None


# ═════════════════════════════════════════════════════════════════════════════
# _gather_report_data (integration smoke test)
# ═════════════════════════════════════════════════════════════════════════════


class TestGatherReportData:
    def test_contains_expected_sections(self) -> None:
        """The top-level report always has all 7 sections."""
        with (
            patch("ajo.commands.report._gather_config", return_value=None),
            patch("ajo.commands.report._gather_django_info", return_value=None),
            patch("ajo.commands.report._gather_update_info", return_value=None),
        ):
            data = _gather_report_data()

        expected_sections = {
            "generated_at",
            "system",
            "python",
            "ajo",
            "terminal",
            "config",
            "django_project",
            "update_check",
        }
        assert expected_sections.issubset(data.keys())


# ═════════════════════════════════════════════════════════════════════════════
# Output formatting
# ═════════════════════════════════════════════════════════════════════════════


SAMPLE_REPORT = {
    "generated_at": "2026-07-07T12:00:00+00:00",
    "system": {"os": "Linux", "os_release": "6.8.0", "machine": "x86_64"},
    "python": {
        "version": "3.13.3",
        "full_version": "3.13.3 (main, ...)",
        "executable": "/usr/bin/python3",
    },
    "ajo": {
        "version": "3.3.0",
        "install_path": "/home/user/ajo-cli",
        "environment": "uv",
    },
    "terminal": {"is_tty": True, "color_depth": "truecolor"},
    "config": {"nerd_fonts": True, "api_key": "***REDACTED***"},
    "django_project": {
        "project_name": "myproject",
        "django_version": "5.1.3",
        "models_count": 5,
        "apps_count": 3,
        "apps": ["auth", "polls", "api"],
        "middleware_count": 3,
        "url_patterns_count": 4,
    },
    "update_check": {"latest_version": "9.9.9", "update_available": True},
}


class TestFormatMarkdown:
    def test_includes_section_headings(self) -> None:
        md = _format_markdown(SAMPLE_REPORT)
        assert "# ajo Diagnostic Report" in md
        assert "## System" in md
        assert "## Python" in md
        assert "## ajo CLI" in md
        assert "## Terminal" in md
        assert "## Configuration" in md
        assert "## Django Project" in md
        assert "## Update Check" in md

    def test_includes_redacted_values(self) -> None:
        md = _format_markdown(SAMPLE_REPORT)
        assert "api_key" in md
        assert "REDACTED" in md
        assert "should-be-hidden" not in md

    def test_includes_django_info(self) -> None:
        md = _format_markdown(SAMPLE_REPORT)
        assert "myproject" in md
        assert "5.1.3" in md

    def test_includes_update_info(self) -> None:
        md = _format_markdown(SAMPLE_REPORT)
        assert "9.9.9" in md
        assert "update_available" in md


class TestWriteJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "report.json"
        _write_json(SAMPLE_REPORT, path)

        assert path.is_file()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["system"]["os"] == "Linux"
        assert loaded["config"]["api_key"] == "***REDACTED***"


class TestWriteMarkdown:
    def test_writes_markdown_file(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        _write_markdown(SAMPLE_REPORT, path)

        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "# ajo Diagnostic Report" in content
        assert "### Linux" in content or "Linux" in content


class TestPrintReport:
    def test_writes_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        _print_report(SAMPLE_REPORT)
        captured = capsys.readouterr()
        assert "ajo Diagnostic Report" in captured.out


# ═════════════════════════════════════════════════════════════════════════════
# _copy_to_clipboard
# ═════════════════════════════════════════════════════════════════════════════


class TestCopyToClipboard:
    def test_raises_import_error_when_pyperclip_missing(self) -> None:
        """When pyperclip is not installed, ImportError is raised."""
        with patch.dict("sys.modules", {"pyperclip": None}):
            with pytest.raises(ImportError):
                _copy_to_clipboard(SAMPLE_REPORT)


# ═════════════════════════════════════════════════════════════════════════════
# run — integration
# ═════════════════════════════════════════════════════════════════════════════


class MockArgs:
    def __init__(
        self,
        output: str | None = None,
        clipboard: bool = False,
        stdout: bool = False,
    ) -> None:
        self.output = output
        self.clipboard = clipboard
        self.stdout = stdout


class TestRun:
    def test_stdout_returns_zero(self, capsys: pytest.CaptureFixture) -> None:
        """run() with no flags prints to stdout and returns 0."""
        with (
            patch("ajo.commands.report._gather_report_data") as mock_gather,
        ):
            mock_gather.return_value = SAMPLE_REPORT
            result = run(MockArgs(stdout=False))  # default → stdout

        assert result == 0
        captured = capsys.readouterr()
        assert "ajo Diagnostic Report" in captured.out

    def test_output_json(self, tmp_path: Path) -> None:
        """--output report.json saves valid JSON."""
        out = tmp_path / "report.json"
        with patch("ajo.commands.report._gather_report_data") as mock_gather:
            mock_gather.return_value = SAMPLE_REPORT
            result = run(MockArgs(output=str(out)))

        assert result == 0
        assert out.is_file()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["system"]["os"] == "Linux"

    def test_output_markdown(self, tmp_path: Path) -> None:
        """--output report.md saves Markdown."""
        out = tmp_path / "report.md"
        with patch("ajo.commands.report._gather_report_data") as mock_gather:
            mock_gather.return_value = SAMPLE_REPORT
            result = run(MockArgs(output=str(out)))

        assert result == 0
        content = out.read_text(encoding="utf-8")
        assert "ajo Diagnostic Report" in content

    def test_clipboard_without_pyperclip_falls_back(self, capsys) -> None:
        """--clipboard without pyperclip prints error + stdout."""
        with (
            patch("ajo.commands.report._gather_report_data") as mock_gather,
            patch("ajo.commands.report._copy_to_clipboard", side_effect=ImportError),
        ):
            mock_gather.return_value = SAMPLE_REPORT
            result = run(MockArgs(clipboard=True))

        assert result == 0
        captured = capsys.readouterr()
        assert "pyperclip" in captured.err
        assert "ajo Diagnostic Report" in captured.out
