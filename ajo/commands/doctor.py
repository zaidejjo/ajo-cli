"""``ajo doctor`` — System health check.

Reports tool versions, Python environment type, terminal capabilities,
and configuration health.  Reuses the existing
:mod:`ajo.detector.prereqs` module for binary detection.

Usage::

    ajo doctor
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ajo.core.environment import (
    detect_environment_name,
    environment_display as env_display,
)


# ── Environment detection (delegates to ajo.core.environment) ──────────────


def _detect_environment() -> str:
    """Return the short name of the current Python environment.

    Delegates to :func:`ajo.core.environment.detect_environment_name`.
    Returns one of: ``"virtualenv"``, ``"uv"``, ``"pipx"``, ``"conda"``,
    ``"global"``.
    """
    return detect_environment_name()


def _environment_display() -> str:
    """Return a display string for the environment (e.g. ``virtualenv (.venv)``).

    Delegates to :func:`ajo.core.environment.environment_display`.
    """
    return env_display()


# ── Individual checks ─────────────────────────────────────────────────────


def _check_python() -> dict[str, Any]:
    """Check Python version >= 3.10."""
    ok = sys.version_info >= (3, 10)
    version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    return {
        "name": "Python",
        "ok": ok,
        "value": version,
        "hint": "3.10+" if not ok else None,
    }


def _check_environment() -> dict[str, Any]:
    """Detect the Python environment type."""
    display = _environment_display()
    return {
        "name": "Environment",
        "ok": True,  # Any env type is valid
        "value": display,
    }


def _check_binary(
    binary: str, display_name: str, *, requirement: str = ""
) -> dict[str, Any]:
    """Check a binary tool: available + version.

    Args:
        binary: Executable name (e.g. ``"uv"``).
        display_name: Human-readable name (e.g. ``"uv"``).
        requirement: Optional expected version hint.

    Returns:
        A check result dict.
    """
    from shutil import which

    path = which(binary)
    if path is None:
        return {
            "name": display_name,
            "ok": False,
            "value": "Not installed",
            "hint": f"Install {display_name}" if requirement else None,
        }

    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            version = (result.stdout or result.stderr).strip().split("\n")[0]
            return {
                "name": display_name,
                "ok": True,
                "value": version,
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
        pass

    return {
        "name": display_name,
        "ok": True,  # binary exists but couldn't read version
        "value": "Available",
    }


def _check_pip() -> dict[str, Any]:
    """Check pip availability and version."""
    from shutil import which

    # uv-managed pythons may not have pip directly
    pip_path = which("pip") or which("pip3")
    if pip_path is None:
        return {
            "name": "pip",
            "ok": True,  # optional when uv is available
            "value": "Not found (uv alternative)",
        }

    try:
        result = subprocess.run(
            [pip_path, "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            # Extract just the version number from "pip 25.0 from ..."
            first_line = result.stdout.strip().split("\n")[0]
            return {
                "name": "pip",
                "ok": True,
                "value": first_line,
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
        pass

    return {
        "name": "pip",
        "ok": True,
        "value": "Available",
    }


def _check_terminal() -> list[dict[str, Any]]:
    """Check terminal capabilities (colour depth, Nerd Fonts).

    Returns a list of check results.
    """
    results: list[dict[str, Any]] = []

    try:
        from ajo.ui.capabilities import has_nerd_fonts, has_true_color

        nerd_fonts = has_nerd_fonts()
        results.append(
            {
                "name": "Nerd Font",
                "ok": nerd_fonts,
                "value": "Installed" if nerd_fonts else "Not detected",
            }
        )

        true_color = has_true_color()
        results.append(
            {
                "name": "TrueColor",
                "ok": true_color,
                "value": "Supported" if true_color else "Not supported",
            }
        )
    except Exception:
        results.append(
            {
                "name": "Terminal",
                "ok": True,
                "value": "Detection unavailable",
            }
        )

    return results


def _check_config() -> dict[str, Any]:
    """Validate the configuration file health."""
    try:
        from ajo.core.config import CONFIG_DIR, CONFIG_FILE

        if not CONFIG_DIR.exists():
            return {
                "name": "Config",
                "ok": True,
                "value": f"Not yet created ({CONFIG_DIR})",
            }

        if not CONFIG_FILE.exists():
            return {
                "name": "Config",
                "ok": True,
                "value": "Directory exists, no config file",
            }

        raw = CONFIG_FILE.read_text(encoding="utf-8")
        import json

        data = json.loads(raw)
        # Basic schema validation
        if "nerd_fonts" not in data:
            return {
                "name": "Config",
                "ok": False,
                "value": str(CONFIG_FILE),
                "hint": "Missing required keys",
            }

        return {
            "name": "Config",
            "ok": True,
            "value": str(CONFIG_FILE),
        }

    except json.JSONDecodeError:
        return {
            "name": "Config",
            "ok": False,
            "value": str(CONFIG_FILE),
            "hint": "Invalid JSON",
        }
    except (PermissionError, OSError) as exc:
        return {
            "name": "Config",
            "ok": False,
            "value": str(CONFIG_FILE),
            "hint": str(exc),
        }
    except Exception:
        return {
            "name": "Config",
            "ok": True,
            "value": "Check skipped",
        }


# ── Result rendering ──────────────────────────────────────────────────────


def _format_check(check: dict[str, Any], prefix: str = "") -> str:
    """Format a single check result as a plain-text line.

    Args:
        check: A result dict with keys ``name``, ``ok``, ``value``,
               and optional ``hint``.
        prefix: Indentation prefix.

    Returns:
        A single-line string (no trailing newline).
    """
    icon = "✓" if check["ok"] else "✗"
    hint = f"  ({check['hint']})" if check.get("hint") else ""
    return f"{prefix}{icon} {check['name']}: {check['value']}{hint}"


def _render_plain(checks: list[dict[str, Any] | list[dict[str, Any]]]) -> str:
    """Render all checks as plain text.

    Args:
        checks: Flat list of check dicts or nested lists.

    Returns:
        Multi-line string.
    """
    lines: list[str] = []
    for entry in checks:
        if isinstance(entry, list):
            # Nested group
            for item in entry:
                lines.append("  " + _format_check(item))
        else:
            lines.append(_format_check(entry))
    return "\n".join(lines)


def _render_rich(checks: list[dict[str, Any] | list[dict[str, Any]]]) -> Any:
    """Render all checks as a Rich ``Tree``.

    Returns a ``rich.tree.Tree`` or ``Panel`` ready for ``console.print()``.
    """
    from rich.style import Style
    from rich.text import Text
    from rich.tree import Tree

    tree = Tree(
        Text("AJO Doctor", style=Style(bold=True)),
        guide_style="dim",
    )

    for entry in checks:
        if isinstance(entry, list):
            # Nested group — flatten into tree
            for item in entry:
                _add_check_to_tree(tree, item)
        else:
            _add_check_to_tree(tree, entry)

    return tree


def _add_check_to_tree(tree: Any, check: dict[str, Any]) -> None:
    """Add a single check result as a child node to *tree*."""
    icon = "✓" if check["ok"] else "✗"
    color = "green" if check["ok"] else "red"
    label = f"[{color}]{icon}[/] {check['name']}: [bold]{check['value']}[/]"
    if check.get("hint"):
        label += f" [dim]({check['hint']})[/]"
    tree.add(label)


# ── Public entry point ────────────────────────────────────────────────────


def run(args: Any) -> int:
    """Execute ``ajo doctor`` — the system health check.

    Args:
        args: The parsed ``argparse.Namespace`` (unused by doctor).

    Returns:
        ``0`` on success, ``1`` if any critical check failed.
    """
    # ── Run all checks ─────────────────────────────────────────────────
    checks: list[dict[str, Any] | list[dict[str, Any]]] = [
        _check_python(),
        _check_environment(),
        _check_binary("uv", "uv"),
        _check_binary("git", "git"),
        _check_binary("gh", "GitHub CLI"),
        _check_pip(),
        *_check_terminal(),  # unpacks list into flat list
        _check_config(),
    ]

    # ── Render ─────────────────────────────────────────────────────────
    try:
        # Attempt Rich rendering (beautiful tree)
        from ajo.cli import console  # noqa: PLC0415 — lazy

        tree = _render_rich(checks)
        console.print()
        console.print(tree)
        console.print()
    except Exception:
        # Fall back to plain text if console is not available
        text = _render_plain(checks)
        print(text, file=sys.stderr)

    # ── Determine exit code ────────────────────────────────────────────
    any_failed = False
    for entry in checks:
        if isinstance(entry, list):
            if any(item.get("ok") is False for item in entry):
                any_failed = True
                break
        elif entry.get("ok") is False:
            any_failed = True
            break

    return 1 if any_failed else 0
