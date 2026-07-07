"""``ajo report`` — Comprehensive diagnostic report.

Generates a shareable report containing OS, Python, ajo, terminal,
configuration (with secrets redacted), Django project info, and
update status.

Usage::

    ajo report                     # Print to stdout (markdown)
    ajo report --stdout            # Explicit stdout (default)
    ajo report --output diag.json  # Save as JSON
    ajo report --output diag.md    # Save as Markdown
    ajo report --clipboard         # Copy to system clipboard
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ajo import __version__ as ajo_version

logger = logging.getLogger(__name__)

# ── Keys whose values are redacted in the report ───────────────────────────

SENSITIVE_KEY_PATTERNS: tuple[str, ...] = (
    "secret",
    "token",
    "password",
    "api_key",
    "auth",
    "key",
)


# ═════════════════════════════════════════════════════════════════════════════
# Public entry point
# ═════════════════════════════════════════════════════════════════════════════


def run(args: Any) -> int:
    """Execute the ``ajo report`` subcommand.

    Args:
        args: Parsed ``argparse.Namespace``.

    Returns:
        Exit code: 0 = success, 1 = error.
    """
    data = _gather_report_data()

    output_path = getattr(args, "output", None)
    to_clipboard = getattr(args, "clipboard", False)

    # ── Save to file ────────────────────────────────────────────────────
    if output_path:
        path = Path(output_path)
        ext = path.suffix.lower()
        try:
            if ext == ".json":
                _write_json(data, path)
            else:
                _write_markdown(data, path)
            print(f"Report saved to {path.resolve()}")
        except (OSError, PermissionError) as exc:
            print(f"Error writing report: {exc}", file=sys.stderr)
            return 1
        return 0

    # ── Copy to clipboard ──────────────────────────────────────────────
    if to_clipboard:
        try:
            _copy_to_clipboard(data)
            print("Report copied to clipboard.")
            return 0
        except ImportError:
            print(
                "pyperclip is required for clipboard support.\n"
                "Install it with: pip install pyperclip  (or: uv add pyperclip)\n"
                "Falling back to stdout.\n",
                file=sys.stderr,
            )
            # Fall through to stdout
        except Exception as exc:
            print(f"Clipboard error: {exc}", file=sys.stderr)
            return 1

    # ── Print to stdout ────────────────────────────────────────────────
    _print_report(data)
    return 0


# ═════════════════════════════════════════════════════════════════════════════
# Data gathering
# ═════════════════════════════════════════════════════════════════════════════


def _gather_report_data() -> dict[str, Any]:
    """Gather all diagnostic data into a single dictionary.

    Never raises — all failures are captured as ``None`` / ``"N/A"`` / ``"unknown"``.
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": _gather_system_info(),
        "python": _gather_python_info(),
        "ajo": _gather_ajo_info(),
        "terminal": _gather_terminal_info(),
        "config": _gather_config(),
        "django_project": _gather_django_info(),
        "update_check": _gather_update_info(),
    }


def _gather_system_info() -> dict[str, Any]:
    """Gather OS-level information."""
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
    }


def _gather_python_info() -> dict[str, Any]:
    """Gather Python runtime information."""
    return {
        "version": sys.version.split()[0],
        "full_version": sys.version.strip(),
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
    }


def _gather_ajo_info() -> dict[str, Any]:
    """Gather ajo-cli installation information."""
    try:
        from ajo.core.environment import (  # noqa: PLC0415
            detect_environment,
            environment_display,
        )

        env = detect_environment()
        env_name = environment_display(env)
    except Exception:
        env_name = "unknown"

    return {
        "version": ajo_version,
        "install_path": str(Path(__file__).resolve().parent.parent.parent),
        "environment": env_name,
    }


def _gather_terminal_info() -> dict[str, Any]:
    """Gather terminal color and capabilities."""
    info: dict[str, Any] = {
        "term_env": os.environ.get("TERM", "N/A"),
        "color_term_env": os.environ.get("COLORTERM", "N/A"),
        "is_tty": sys.stdout.isatty(),
        "color_depth": _detect_color_depth(),
        "nerd_font_detected": None,
    }

    # Nerd Font detection from config
    try:
        from ajo.core.config import get_config  # noqa: PLC0415

        cfg = get_config()
        if cfg is not None:
            nf = cfg.get("nerd_fonts")
            if nf is not None:
                info["nerd_font_detected"] = bool(nf)
    except Exception:
        pass

    return info


def _detect_color_depth() -> str:
    """Detect terminal color depth in a portable way."""
    if not sys.stdout.isatty():
        return "none (piped)"

    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return "truecolor"
    if colorterm in ("256color",):
        return "256"

    term = os.environ.get("TERM", "").lower()
    if "truecolor" in term or "24bit" in term:
        return "truecolor"
    if "256" in term:
        return "256"
    if "color" in term:
        return "16"

    # Fallback heuristic: if COLORTERM is unset but TERM is xterm,
    # modern terminals almost always support 256+
    if "xterm" in term:
        return "256"

    return "unknown"


def _gather_config() -> dict[str, Any] | None:
    """Gather ajo configuration with secrets redacted.

    Returns ``None`` if the config module is unavailable.
    """
    try:
        from ajo.core.config import CONFIG_FILE, ConfigManager  # noqa: PLC0415

        config = ConfigManager()
        raw: dict[str, Any] = dict(config._data) if hasattr(config, "_data") else {}  # noqa: SLF001
        redacted = _redact_sensitive_values(raw)
        redacted["_config_file"] = str(CONFIG_FILE)
        redacted["_config_file_exists"] = CONFIG_FILE.is_file()
        return redacted
    except Exception:
        return None


def _redact_sensitive_values(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with sensitive values replaced.

    A key is considered sensitive if it contains any of the
    :data:`SENSITIVE_KEY_PATTERNS` (case-insensitive match).

    Args:
        data: The raw config dictionary.

    Returns:
        A new dict with sensitive values replaced by ``"***REDACTED***"``.
    """
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = _redact_sensitive_values(value)
        else:
            redacted[key] = value
    return redacted


def _gather_django_info() -> dict[str, Any] | None:
    """Gather Django project information by reusing :mod:`ajo.commands.scan`.

    Returns ``None`` if not in a Django project or if scan is unavailable.
    """
    try:
        from ajo.commands.scan import (  # noqa: PLC0415
            _gather_scan_data,
        )

        scan_data = _gather_scan_data()
        if not scan_data.get("is_django_project"):
            return None

        return {
            "project_name": scan_data.get("project_name", "N/A"),
            "django_version": scan_data.get("django_version", "N/A"),
            "models_count": scan_data.get("models_count", 0),
            "apps_count": scan_data.get("apps_count", 0),
            "apps": scan_data.get("apps", []),
            "middleware_count": scan_data.get("middleware_count", 0),
            "url_patterns_count": scan_data.get("url_patterns_count", 0),
            "git_branch": scan_data.get("git_branch", "N/A"),
            "server_running": scan_data.get("server_running", False),
            "venv_active": scan_data.get("venv_active", False),
        }
    except Exception:
        return None


def _gather_update_info() -> dict[str, Any] | None:
    """Gather cached update-check information.

    Returns ``None`` if no update check has been performed yet.
    """
    try:
        from ajo.core.updater import get_cached_update  # noqa: PLC0415

        result = get_cached_update()
        if result is None:
            return None
        latest, is_newer = result
        return {
            "latest_version": latest,
            "current_version": ajo_version,
            "update_available": is_newer,
        }
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Output rendering
# ═════════════════════════════════════════════════════════════════════════════


def _write_json(data: dict[str, Any], path: Path) -> None:
    """Write the report as pretty-printed JSON."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _write_markdown(data: dict[str, Any], path: Path) -> None:
    """Write the report as a human-readable Markdown document."""
    md = _format_markdown(data)
    path.write_text(md, encoding="utf-8")


def _print_report(data: dict[str, Any]) -> None:
    """Print the report to stdout as Markdown."""
    sys.stdout.write(_format_markdown(data))


def _format_markdown(data: dict[str, Any]) -> str:
    """Format the report data as a Markdown string.

    Args:
        data: The report data dictionary.

    Returns:
        A UTF-8 Markdown string.
    """
    lines: list[str] = []
    _md_h1(lines, f"ajo Diagnostic Report")
    _md_meta(lines, data)

    _md_h2(lines, "System")
    _md_dict(lines, data.get("system", {}))

    _md_h2(lines, "Python")
    _md_dict(lines, data.get("python", {}))

    _md_h2(lines, "ajo CLI")
    _md_dict(lines, data.get("ajo", {}))

    _md_h2(lines, "Terminal")
    _md_dict(lines, data.get("terminal", {}))

    _md_h2(lines, "Configuration")
    config_data = data.get("config")
    if config_data:
        _md_dict(lines, config_data)
    else:
        lines.append("_Config not available._\n")

    _md_h2(lines, "Django Project")
    django_data = data.get("django_project")
    if django_data:
        _md_dict(lines, django_data)
    else:
        lines.append("_Not in a Django project (or detection unavailable)._  \n")

    _md_h2(lines, "Update Check")
    update_data = data.get("update_check")
    if update_data:
        _md_dict(lines, update_data)
    else:
        lines.append("_No update check performed yet._  \n")

    lines.append("---\n")
    lines.append(f"_Report generated: {data.get('generated_at', 'N/A')}_  \n")
    return "\n".join(lines)


def _md_h1(lines: list[str], text: str) -> None:
    lines.append(f"# {text}\n")


def _md_h2(lines: list[str], text: str) -> None:
    lines.append(f"## {text}\n")


def _md_meta(lines: list[str], data: dict[str, Any]) -> None:
    """Add a metadata block after the H1."""
    generated = data.get("generated_at", "N/A")
    lines.append(f"- **Generated:** {generated}")
    lines.append(f"- **ajo version:** {data.get('ajo', {}).get('version', 'N/A')}")
    lines.append(f"- **Python:** {data.get('python', {}).get('version', 'N/A')}")
    lines.append(
        f"- **OS:** {data.get('system', {}).get('os', 'N/A')} {data.get('system', {}).get('os_release', '')}"
    )
    lines.append("")


def _md_dict(lines: list[str], data: dict[str, Any]) -> None:
    """Append key-value pairs as a Markdown list.

    Nested dicts are indented.
    """
    for key, value in data.items():
        # Skip internal keys
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            lines.append(f"- **{key}:**")
            for k, v in value.items():
                if not k.startswith("_"):
                    lines.append(f"  - {k}: `{v}`")
        elif isinstance(value, list):
            if value:
                items = ", ".join(str(x) for x in value[:12])
                if len(value) > 12:
                    items += f" … (+{len(value) - 12} more)"
                lines.append(f"- **{key}:** {items}")
            else:
                lines.append(f"- **{key}:** _(empty)_")
        elif value is None:
            lines.append(f"- **{key}:** N/A")
        elif isinstance(value, bool):
            lines.append(f"- **{key}:** {'yes' if value else 'no'}")
        else:
            lines.append(f"- **{key}:** `{value}`")
    lines.append("")


def _copy_to_clipboard(data: dict[str, Any]) -> None:
    """Copy the report to the system clipboard as Markdown.

    Raises ``ImportError`` if ``pyperclip`` is not installed.
    """
    try:
        import pyperclip  # noqa: PLC0415, F811
    except ImportError:
        raise  # Re-raise so the caller can handle it

    md = _format_markdown(data)
    pyperclip.copy(md)
