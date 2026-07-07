"""Tests for ajo.core.environment.

All detection functions accept optional override parameters so they can
be tested without mocking ``os.environ`` / ``sys`` directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ajo.core.environment import (
    PythonEnvironment,
    apply_run_prefix,
    detect_environment,
    detect_environment_name,
    environment_display,
    install_command,
    run_command_prefix,
    upgrade_command,
)


# =============================================================================
# detect_environment
# =============================================================================


class TestDetectEnvironment:
    """Tests for the core detection logic."""

    def test_global(self) -> None:
        """No env vars → GLOBAL."""
        env = detect_environment(environ={}, prefix="/usr", base_prefix="/usr")
        assert env == PythonEnvironment.GLOBAL

    def test_virtualenv(self) -> None:
        """VIRTUAL_ENV set → VIRTUALENV."""
        env = detect_environment(
            environ={"VIRTUAL_ENV": "/path/to/.venv"},
            prefix="/path/to/.venv",
            base_prefix="/usr",
        )
        assert env == PythonEnvironment.VIRTUALENV

    def test_virtualenv_via_prefix_diff(self) -> None:
        """sys.prefix != sys.base_prefix without VIRTUAL_ENV → VIRTUALENV."""
        env = detect_environment(
            environ={},
            prefix="/path/to/.venv",
            base_prefix="/usr",
        )
        assert env == PythonEnvironment.VIRTUALENV

    def test_uv(self) -> None:
        """UV_ACTIVE set → UV (even if VIRTUAL_ENV also set)."""
        env = detect_environment(
            environ={"UV_ACTIVE": "true", "VIRTUAL_ENV": "/uv/.venv"},
            prefix="/uv/.venv",
            base_prefix="/usr",
        )
        assert env == PythonEnvironment.UV

    def test_conda(self) -> None:
        """CONDA_PREFIX set → CONDA."""
        env = detect_environment(
            environ={"CONDA_PREFIX": "/opt/conda/envs/myenv"},
            prefix="/opt/conda/envs/myenv",
            base_prefix="/opt/conda",
        )
        assert env == PythonEnvironment.CONDA

    def test_pipx(self) -> None:
        """PIPX_ACTIVE set → PIPX."""
        env = detect_environment(
            environ={"PIPX_ACTIVE": "1"},
            executable="/home/user/.local/pipx/venvs/ajo/bin/python",
        )
        assert env == PythonEnvironment.PIPX

    def test_pipx_via_executable_path(self) -> None:
        """Executable under ~/.local/pipx/ without PIPX_ACTIVE → PIPX."""
        env = detect_environment(
            environ={},
            executable=str(
                Path.home() / ".local" / "pipx" / "venvs" / "ajo" / "bin" / "python"
            ),
        )
        assert env == PythonEnvironment.PIPX

    def test_uv_takes_precedence_over_virtualenv(self) -> None:
        """UV_ACTIVE takes precedence even when VIRTUAL_ENV is also set."""
        env = detect_environment(
            environ={"UV_ACTIVE": "1", "VIRTUAL_ENV": "/uv/.venv"},
        )
        assert env == PythonEnvironment.UV


# =============================================================================
# detect_environment_name
# =============================================================================


class TestDetectEnvironmentName:
    """Tests for the string-name convenience wrapper."""

    def test_returns_string(self) -> None:
        name = detect_environment_name(environ={}, prefix="/usr", base_prefix="/usr")
        assert name == "global"
        assert isinstance(name, str)

    @pytest.mark.parametrize(
        ("env_vars", "prefix", "base_prefix", "expected"),
        [
            ({"PIPX_ACTIVE": "1"}, "/usr", "/usr", "pipx"),
            ({"UV_ACTIVE": "true"}, "/usr", "/usr", "uv"),
            ({"CONDA_PREFIX": "/conda"}, "/usr", "/usr", "conda"),
            ({"VIRTUAL_ENV": "/venv"}, "/venv", "/usr", "virtualenv"),
            ({}, "/usr", "/usr", "global"),
        ],
    )
    def test_all_environments(
        self,
        env_vars: dict[str, str],
        prefix: str,
        base_prefix: str,
        expected: str,
    ) -> None:
        name = detect_environment_name(
            environ=env_vars, prefix=prefix, base_prefix=base_prefix
        )
        assert name == expected


# =============================================================================
# environment_display
# =============================================================================


class TestEnvironmentDisplay:
    """Tests for the human-readable display string."""

    def test_global(self) -> None:
        assert (
            environment_display(environ={}, prefix="/usr", base_prefix="/usr")
            == "global"
        )

    def test_virtualenv_with_name(self) -> None:
        display = environment_display(
            environ={"VIRTUAL_ENV": "/home/user/project/.venv"},
        )
        assert display == "virtualenv (.venv)"

    def test_virtualenv_without_name(self) -> None:
        display = environment_display(
            environ={},
            prefix="/custom/venv",
            base_prefix="/usr",
        )
        assert display == "virtualenv"

    def test_conda_with_name(self) -> None:
        display = environment_display(
            environ={"CONDA_PREFIX": "/opt/conda/envs/myenv"},
        )
        assert display == "conda (myenv)"

    def test_uv(self) -> None:
        display = environment_display(environ={"UV_ACTIVE": "true"})
        assert display == "uv"

    def test_pipx(self) -> None:
        display = environment_display(environ={"PIPX_ACTIVE": "1"})
        assert display == "pipx"


# =============================================================================
# install_command
# =============================================================================


class TestInstallCommand:
    """Tests for subprocess install-command resolution."""

    @pytest.mark.parametrize(
        ("env_vars", "expected_prefix"),
        [
            ({"UV_ACTIVE": "true"}, ["uv", "add"]),
            ({"PIPX_ACTIVE": "1"}, ["pipx", "install"]),
            ({}, ["/usr/bin/python", "-m", "pip", "install"]),
            ({"VIRTUAL_ENV": "/venv"}, ["/usr/bin/python", "-m", "pip", "install"]),
            ({"CONDA_PREFIX": "/conda"}, ["/usr/bin/python", "-m", "pip", "install"]),
        ],
    )
    def test_command_format(
        self, env_vars: dict[str, str], expected_prefix: list[str]
    ) -> None:
        cmd = install_command(environ=env_vars, executable="/usr/bin/python")
        assert cmd == expected_prefix


# =============================================================================
# run_command_prefix
# =============================================================================


class TestRunCommandPrefix:
    """Tests for the run-command prefix helper."""

    def test_uv_returns_prefix(self) -> None:
        prefix = run_command_prefix(environ={"UV_ACTIVE": "true"})
        assert prefix == ["uv", "run"]

    def test_non_uv_returns_none(self) -> None:
        prefix = run_command_prefix(environ={})
        assert prefix is None

    def test_virtualenv_returns_none(self) -> None:
        prefix = run_command_prefix(environ={"VIRTUAL_ENV": "/venv"})
        assert prefix is None


# =============================================================================
# apply_run_prefix
# =============================================================================


class TestApplyRunPrefix:
    """Tests for applying the run prefix to a command."""

    def test_uv_prepends(self) -> None:
        result = apply_run_prefix(
            ["python", "manage.py", "check"],
            environ={"UV_ACTIVE": "true"},
        )
        assert result == ["uv", "run", "python", "manage.py", "check"]

    def test_non_uv_passthrough(self) -> None:
        result = apply_run_prefix(
            ["python", "manage.py", "check"],
            environ={},
        )
        assert result == ["python", "manage.py", "check"]


# =============================================================================
# upgrade_command
# =============================================================================


class TestUpgradeCommand:
    """Tests for the upgrade-command helper."""

    def test_uv(self) -> None:
        cmd = upgrade_command(environ={"UV_ACTIVE": "true"})
        assert cmd == ["uv", "tool", "upgrade", "ajo-cli"]

    def test_pipx(self) -> None:
        cmd = upgrade_command(environ={"PIPX_ACTIVE": "1"})
        assert cmd == ["pipx", "upgrade", "ajo-cli"]

    def test_pip(self) -> None:
        cmd = upgrade_command(environ={}, executable="/usr/bin/python3")
        assert cmd == [
            "/usr/bin/python3",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "ajo-cli",
        ]

    def test_custom_package(self) -> None:
        cmd = upgrade_command(
            package="some-other-pkg",
            environ={"UV_ACTIVE": "true"},
        )
        assert cmd == ["uv", "tool", "upgrade", "some-other-pkg"]
