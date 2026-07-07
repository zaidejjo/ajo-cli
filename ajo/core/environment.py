"""Python environment detection and subprocess delegation.

Detects whether ``ajo`` is running under ``virtualenv``, ``uv``, ``pipx``,
``conda``, or system-wide Python (``global``).  Provides helpers for
selecting the correct package-install command and run-prefix based on
the active environment.

Usage::

    from ajo.core.environment import detect_environment, PythonEnvironment

    env = detect_environment()
    print(env)                           # PythonEnvironment.UV
    print(environment_display())         # "uv"
    print(" ".join(install_command()))   # "uv add"
"""

from __future__ import annotations

import os
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Sequence


# =============================================================================
# ENUM
# =============================================================================


class PythonEnvironment(Enum):
    """Identifies the Python environment manager in use."""

    GLOBAL = auto()  # pip install --system (or no virtual env active)
    VIRTUALENV = auto()  # source .venv/bin/activate
    UV = auto()  # uv run / uv tool
    PIPX = auto()  # pipx install
    CONDA = auto()  # conda install
    UNKNOWN = auto()  # fallback — should not happen


# =============================================================================
# DETECTION
# =============================================================================

# Sentinel for sys.prefix — we cache it so tests can patch cleanly
_UNSET = object()


def detect_environment(
    *,
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    prefix: str | None = None,
    base_prefix: str | None = None,
) -> PythonEnvironment:
    """Detect the current Python environment manager.

    The detection logic uses environment variables as canonical signals:

    * ``PIPX_ACTIVE`` or executable under ``~/.local/pipx/`` → ``PIPX``
    * ``UV_ACTIVE`` → ``UV``
    * ``CONDA_PREFIX`` → ``CONDA``
    * ``VIRTUAL_ENV`` or ``sys.prefix != sys.base_prefix`` → ``VIRTUALENV``
    * Otherwise → ``GLOBAL``

    Every parameter is optional — when omitted the real ``os.environ`` /
    ``sys`` values are used.  This makes the function fully testable without
    monkey-patching built-in modules.

    Args:
        environ: Environment variable mapping (defaults to ``os.environ``).
        executable: ``sys.executable`` path (defaults to the real one).
        prefix: ``sys.prefix`` (defaults to the real one).
        base_prefix: ``sys.base_prefix`` (defaults to the real one).

    Returns:
        A :class:`PythonEnvironment` member.
    """
    env = os.environ if environ is None else environ
    exe = sys.executable if executable is None else executable
    pref = sys.prefix if prefix is None else prefix
    base_pref = sys.base_prefix if base_prefix is None else base_prefix

    # ── pipx ───────────────────────────────────────────────────────────
    pipx_active = env.get("PIPX_ACTIVE")
    pipx_home = str(Path.home() / ".local" / "pipx")
    if pipx_active or str(Path(exe)).startswith(pipx_home):
        return PythonEnvironment.PIPX

    # ── uv (must check before virtualenv — uv sets VIRTUAL_ENV too) ───
    if env.get("UV_ACTIVE"):
        return PythonEnvironment.UV

    # ── conda ─────────────────────────────────────────────────────────
    if env.get("CONDA_PREFIX"):
        return PythonEnvironment.CONDA

    # ── virtualenv ────────────────────────────────────────────────────
    if env.get("VIRTUAL_ENV") or pref != base_pref:
        return PythonEnvironment.VIRTUALENV

    # ── fallback ──────────────────────────────────────────────────────
    return PythonEnvironment.GLOBAL


def detect_environment_name(
    *,
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    prefix: str | None = None,
    base_prefix: str | None = None,
) -> str:
    """Return a short string name for the current environment.

    Returns one of ``"pipx"``, ``"uv"``, ``"conda"``, ``"virtualenv"``,
    ``"global"``.

    This is a convenience wrapper around :func:`detect_environment` for
    callers that need a simple string (e.g. serialisation, the ``doctor``
    command).
    """
    mapping = {
        PythonEnvironment.PIPX: "pipx",
        PythonEnvironment.UV: "uv",
        PythonEnvironment.CONDA: "conda",
        PythonEnvironment.VIRTUALENV: "virtualenv",
        PythonEnvironment.GLOBAL: "global",
        PythonEnvironment.UNKNOWN: "global",
    }
    env = detect_environment(
        environ=environ,
        executable=executable,
        prefix=prefix,
        base_prefix=base_prefix,
    )
    return mapping[env]


def environment_display(
    *,
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    prefix: str | None = None,
    base_prefix: str | None = None,
) -> str:
    """Return a human-readable display string for the current environment.

    Includes the environment path suffix when available::

        "virtualenv (.venv)"
        "conda (myenv)"
        "uv"
        "pipx"
        "global"

    Every parameter is optional and defaults to the real runtime value.
    """
    env = os.environ if environ is None else environ
    name = detect_environment_name(
        environ=env,
        executable=executable,
        prefix=prefix,
        base_prefix=base_prefix,
    )

    venv_path = env.get("VIRTUAL_ENV") or ""
    conda_prefix = env.get("CONDA_PREFIX") or ""

    if name == "virtualenv" and venv_path:
        suffix = Path(venv_path).name
        return f"virtualenv ({suffix})"
    if name == "conda" and conda_prefix:
        suffix = Path(conda_prefix).name
        return f"conda ({suffix})"
    return name


# =============================================================================
# SUBPROCESS DELEGATION HELPERS
# =============================================================================


def install_command(
    *,
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    prefix: str | None = None,
    base_prefix: str | None = None,
) -> list[str]:
    """Return the appropriate ``install`` command for the current environment.

    Returns a command list suitable for subprocess execution:

    * **uv** → ``["uv", "add"]``
    * **pipx** → ``["pipx", "install"]``
    * **virtualenv / conda / global** → ``[sys.executable, "-m", "pip", "install"]``

    Args:
        environ: Environment override (for testing).
        executable: ``sys.executable`` override.
        prefix: ``sys.prefix`` override.
        base_prefix: ``sys.base_prefix`` override.

    Returns:
        A list of strings representing the install command (without the
        package name).
    """
    env = detect_environment(
        environ=environ,
        executable=executable,
        prefix=prefix,
        base_prefix=base_prefix,
    )

    if env == PythonEnvironment.UV:
        return ["uv", "add"]

    if env == PythonEnvironment.PIPX:
        return ["pipx", "install"]

    exe = sys.executable if executable is None else executable
    return [exe, "-m", "pip", "install"]


def upgrade_command(
    *,
    package: str = "ajo-cli",
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    prefix: str | None = None,
    base_prefix: str | None = None,
) -> list[str]:
    """Return the command to upgrade *package* in the current environment.

    Returns:

    * **uv** → ``["uv", "tool", "upgrade", package]``
    * **pipx** → ``["pipx", "upgrade", package]``
    * **virtualenv / conda / global** → ``[sys.executable, "-m", "pip", "install", "--upgrade", package]``

    Args:
        package: Package name to upgrade (default ``"ajo-cli"``).
        environ: Environment override (for testing).
        executable: ``sys.executable`` override.
        prefix: ``sys.prefix`` override.
        base_prefix: ``sys.base_prefix`` override.

    Returns:
        A command list ready for ``subprocess.run`` / ``_run_command``.
    """
    env = detect_environment(
        environ=environ,
        executable=executable,
        prefix=prefix,
        base_prefix=base_prefix,
    )

    if env == PythonEnvironment.UV:
        return ["uv", "tool", "upgrade", package]

    if env == PythonEnvironment.PIPX:
        return ["pipx", "upgrade", package]

    exe = sys.executable if executable is None else executable
    return [exe, "-m", "pip", "install", "--upgrade", package]


def run_command_prefix(
    *,
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    prefix: str | None = None,
    base_prefix: str | None = None,
) -> list[str] | None:
    """Return a command prefix for running tools inside the environment.

    * **uv** → ``["uv", "run"]``
    * **others** → ``None`` (run directly)

    Returns ``None`` when no prefix is needed — the caller should execute
    the command as-is.
    """
    env = detect_environment(
        environ=environ,
        executable=executable,
        prefix=prefix,
        base_prefix=base_prefix,
    )

    if env == PythonEnvironment.UV:
        return ["uv", "run"]

    return None


def apply_run_prefix(
    command: Sequence[str],
    **kwargs: object,
) -> list[str]:
    """Prepend the environment run-prefix to *command* if applicable.

    In a **uv** environment this returns ``["uv", "run", *command]``.
    In all other environments the command is returned unchanged.

    This is a convenience wrapper around :func:`run_command_prefix`.
    """
    prefix = run_command_prefix(**kwargs)
    if prefix is not None:
        return [*prefix, *command]
    return list(command)
