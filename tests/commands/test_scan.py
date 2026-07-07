"""Tests for ajo.commands.scan.

All subprocess and filesystem interactions are isolated so tests never
require a real Django project to be present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ajo.commands.scan import (
    _check_config_status,
    _count_middleware,
    _count_url_patterns,
    _detect_django_version,
    _gather_scan_data,
    _render_json,
    _render_plain,
    run,
)


# ═════════════════════════════════════════════════════════════════════════════
# _count_middleware
# ═════════════════════════════════════════════════════════════════════════════


class TestCountMiddleware:
    def test_counts_middleware(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.py"
        settings.write_text(
            "MIDDLEWARE = [\n"
            "    'django.middleware.security.SecurityMiddleware',\n"
            "    'django.contrib.sessions.middleware.SessionMiddleware',\n"
            "    'django.middleware.common.CommonMiddleware',\n"
            "]\n"
        )
        assert _count_middleware(settings) == 3

    def test_empty_list(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.py"
        settings.write_text("MIDDLEWARE = []\n")
        assert _count_middleware(settings) == 0

    def test_no_middleware_key(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.py"
        settings.write_text("INSTALLED_APPS = []\n")
        assert _count_middleware(settings) == 0

    def test_file_not_found(self) -> None:
        assert _count_middleware(Path("/nonexistent/settings.py")) == 0

    def test_ignores_comments(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.py"
        settings.write_text(
            "MIDDLEWARE = [\n"
            "    # Comment line\n"
            "    'django.middleware.security.SecurityMiddleware',\n"
            "]\n"
        )
        assert _count_middleware(settings) == 1


# ═════════════════════════════════════════════════════════════════════════════
# _count_url_patterns
# ═════════════════════════════════════════════════════════════════════════════


class TestCountUrlPatterns:
    def test_counts_path_calls(self, tmp_path: Path) -> None:
        urls = tmp_path / "urls.py"
        urls.write_text(
            "urlpatterns = [\n"
            "    path('admin/', admin.site.urls),\n"
            "    path('api/', include('api.urls')),\n"
            "    re_path(r'^api/v2/', include('api_v2.urls')),\n"
            "]\n"
        )
        assert _count_url_patterns(urls) == 3

    def test_empty_urlpatterns(self, tmp_path: Path) -> None:
        urls = tmp_path / "urls.py"
        urls.write_text("urlpatterns = []\n")
        assert _count_url_patterns(urls) == 0

    def test_file_not_found(self) -> None:
        assert _count_url_patterns(Path("/nonexistent/urls.py")) == 0

    def test_no_urlpatterns(self, tmp_path: Path) -> None:
        urls = tmp_path / "urls.py"
        urls.write_text("# just a comment\n")
        assert _count_url_patterns(urls) == 0


# ═════════════════════════════════════════════════════════════════════════════
# _detect_django_version
# ═════════════════════════════════════════════════════════════════════════════


class TestDetectDjangoVersion:
    def test_returns_version_string(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "5.1.3\n"
            mock_run.return_value = mock_proc

            version = _detect_django_version(tmp_path)

        assert version == "5.1.3"

    def test_subprocess_failure(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stdout = ""
            mock_run.return_value = mock_proc

            version = _detect_django_version(tmp_path)

        assert version == "N/A"

    def test_timeout_returns_na(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutError

            version = _detect_django_version(tmp_path)

        assert version == "N/A"


# ═════════════════════════════════════════════════════════════════════════════
# _check_config_status
# ═════════════════════════════════════════════════════════════════════════════


class TestCheckConfigStatus:
    def test_config_found(self) -> None:
        """Should return a status indicating config was found."""
        with (
            patch("ajo.core.config.CONFIG_FILE") as mock_config_file,
            patch("ajo.core.config.ConfigManager") as mock_mgr,
        ):
            mock_config_file.is_file.return_value = True
            mock_config_file.__str__.return_value = "/fake/path/config.json"

            status, path = _check_config_status()

        assert "Found" in status
        assert path == "/fake/path/config.json"
        mock_mgr.assert_called_once()

    def test_config_not_found(self) -> None:
        """Should return a status indicating config was not created."""
        with patch("ajo.core.config.CONFIG_FILE") as mock_config_file:
            mock_config_file.is_file.return_value = False
            mock_config_file.__str__.return_value = "/fake/path/config.json"

            status, path = _check_config_status()

        assert "Not created" in status


# ═════════════════════════════════════════════════════════════════════════════
# _gather_scan_data (non-Django project)
# ═════════════════════════════════════════════════════════════════════════════


class TestGatherScanData:
    def test_non_django_project(self, tmp_path: Path) -> None:
        """Calling scan from a non-Django directory returns is_django_project=False."""
        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("ajo.commands.scan._check_config_status") as mock_config,
            patch("ajo.commands.scan._detect_environment_name") as mock_env,
        ):
            mock_config.return_value = ("— Not created", "/fake/config.json")
            mock_env.return_value = "virtualenv"

            data = _gather_scan_data()

        assert data["is_django_project"] is False
        assert data["project_name"] == "N/A"
        assert "ajo_version" in data

    def test_includes_ajo_version(self, tmp_path: Path) -> None:
        """Data always includes ajo_version."""
        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("ajo.commands.scan._check_config_status") as mock_config,
            patch("ajo.commands.scan._detect_environment_name") as mock_env,
        ):
            mock_config.return_value = ("✓ Found", "/fake/config.json")
            mock_env.return_value = "uv"

            data = _gather_scan_data()

        assert data["ajo_version"] is not None


# ═════════════════════════════════════════════════════════════════════════════
# run
# ═════════════════════════════════════════════════════════════════════════════


class MockArgs:
    def __init__(self, json_output: bool = False) -> None:
        self.json = json_output


class TestRun:
    def test_returns_zero(self) -> None:
        """run() always returns 0 (non-Django dir is not an error)."""
        with (
            patch("ajo.commands.scan._gather_scan_data") as mock_gather,
        ):
            mock_gather.return_value = {"is_django_project": False}
            result = run(MockArgs(json_output=False))

        assert result == 0

    def test_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """--json flag produces valid JSON output."""
        with (
            patch("ajo.commands.scan._gather_scan_data") as mock_gather,
        ):
            mock_gather.return_value = {
                "is_django_project": True,
                "project_name": "testproj",
                "django_version": "5.1.3",
                "models_count": 5,
                "apps_count": 3,
                "environment": "uv",
            }
            result = run(MockArgs(json_output=True))

        captured = capsys.readouterr()
        assert result == 0
        output = json.loads(captured.out)
        assert output["project_name"] == "testproj"
        assert output["django_version"] == "5.1.3"


# ═════════════════════════════════════════════════════════════════════════════
# _render_plain (fallback output)
# ═════════════════════════════════════════════════════════════════════════════


class TestRenderPlain:
    def test_outputs_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        data = {
            "is_django_project": True,
            "project_name": "testproj",
            "path": "/tmp/testproj",
            "django_version": "5.1.3",
            "models_count": 5,
            "apps_count": 3,
            "environment": "uv",
            "apps": ["django.contrib.admin", "myapp"],
        }
        _render_plain(data)
        captured = capsys.readouterr()
        assert "testproj" in captured.out
        assert "5.1.3" in captured.out
        assert "django.contrib.admin" in captured.out
