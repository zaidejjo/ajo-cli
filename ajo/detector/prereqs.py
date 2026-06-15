"""Optimised prerequisite checks for ajo-cli.

All binary-availability checks use :func:`shutil.which` instead of
subprocess calls, making them practically instant.  Results are cached
in memory for the lifetime of the process since system binaries do not
change at runtime.
"""

from __future__ import annotations

import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple


# ── Public data types ─────────────────────────────────────────────────────────


class PrereqResult(NamedTuple):
    """Aggregated result of all prerequisite checks."""

    all_ok: bool
    python_version: str
    uv_available: bool
    uv_version: str | None
    git_available: bool
    git_version: str | None
    gh_available: bool
    gh_version: str | None


# ── Low-level helpers (public for testing) ────────────────────────────────────


@lru_cache(maxsize=1)
def _binary_path(name: str) -> str | None:
    """Return the full path to *name* on ``PATH``, or ``None``.

    Results are cached in memory (``lru_cache``) so repeated calls
    are free.  Uses :func:`shutil.which` — never spawns a subprocess.
    """
    return shutil.which(name)


def _read_version(binary: str) -> str | None:
    """Try to read the version string for *binary* synchronously.

    This is a lightweight ``subprocess.run`` call that is only invoked
    once per binary due to caching in :func:`check_prerequisites`.
    Prefer this over repeated subprocess calls.
    """
    import subprocess

    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip() or result.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def check_prerequisites() -> PrereqResult:
    """Check all system prerequisites efficiently.

    Binary availability is determined by :func:`shutil.which` (no
    subprocess).  Version strings are read with a single subprocess
    call per binary, cached for the process lifetime.

    Returns:
        A :class:`PrereqResult` named tuple with all fields populated.
    """
    py_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )

    uv_path = _binary_path("uv")
    uv_available = uv_path is not None
    uv_version = _read_version("uv") if uv_available else None

    git_path = _binary_path("git")
    git_available = git_path is not None
    git_version = _read_version("git") if git_available else None

    gh_path = _binary_path("gh")
    gh_available = gh_path is not None
    gh_version = _read_version("gh") if gh_available else None

    return PrereqResult(
        all_ok=uv_available,
        python_version=py_version,
        uv_available=uv_available,
        uv_version=uv_version,
        git_available=git_available,
        git_version=git_version,
        gh_available=gh_available,
        gh_version=gh_version,
    )


def check_uv_installed() -> bool:
    """Fast check — is ``uv`` available on ``PATH``?"""
    return _binary_path("uv") is not None


def check_git_installed() -> bool:
    """Fast check — is ``git`` available on ``PATH``?"""
    return _binary_path("git") is not None


def check_gh_installed() -> bool:
    """Fast check — is ``gh`` available on ``PATH``?"""
    return _binary_path("gh") is not None
