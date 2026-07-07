"""``ajo scan`` — Project Health Card.

Inspects the current Django project and outputs a beautifully formatted
summary using Rich tables and panels.

Shows: Django version, model count, installed apps, middleware count,
discovered URL patterns, config status, and environment context.

Usage::

    ajo scan          # Scan the current directory for a Django project
    ajo scan --json   # Output raw JSON instead of a formatted card
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ajo import __version__ as ajo_version

logger = logging.getLogger(__name__)


# ── Public entry point ─────────────────────────────────────────────────────


def run(args: Any) -> int:
    """Execute the ``ajo scan`` subcommand.

    Args:
        args: Parsed ``argparse.Namespace``.

    Returns:
        Exit code: 0 = success, 1 = error.
    """
    output_json = getattr(args, "json", False)

    # 1. Detect Django project
    data = _gather_scan_data()

    # 2. Render
    if output_json:
        _render_json(data)
    else:
        _render_health_card(data)

    return 0


# ── Data gathering ─────────────────────────────────────────────────────────


def _gather_scan_data() -> dict[str, Any]:
    """Gather all scan data from the current directory.

    Returns a dictionary with all fields needed for the health card.
    Never raises — all failures are captured as ``None`` / ``"N/A"``.
    """
    # Environment context (always available)
    env_name = _detect_environment_name()

    # Config status
    config_status, config_path = _check_config_status()

    # Django project detection
    detector = _create_detector()
    if not detector or not detector.is_django_project:
        return {
            "is_django_project": False,
            "project_name": "N/A",
            "path": str(Path.cwd().resolve()),
            "environment": env_name,
            "config_status": config_status,
            "config_path": config_path,
            "ajo_version": ajo_version,
        }

    # Django project found — gather details
    info = detector.project_info
    manage_py = detector._find_manage_py()  # noqa: SLF001
    project_root = manage_py.parent if manage_py else Path.cwd()
    settings_path = project_root / info.get("settings_module", "config") / "settings.py"
    urls_path = project_root / info.get("settings_module", "config") / "urls.py"

    return {
        "is_django_project": True,
        "project_name": info.get("project_name", "Unknown"),
        "path": str(project_root.resolve()),
        "django_version": _detect_django_version(project_root),
        "models_count": info.get("models_count", 0),
        "apps": info.get("apps", []),
        "apps_count": len(info.get("apps", [])),
        "middleware_count": _count_middleware(settings_path),
        "url_patterns_count": _count_url_patterns(urls_path),
        "git_branch": info.get("git_branch", "N/A"),
        "venv_active": info.get("venv_active", False),
        "server_running": info.get("server_running", False),
        "has_admin": info.get("has_admin", False),
        "has_static": info.get("has_static", False),
        "has_media": info.get("has_media", False),
        "environment": env_name,
        "config_status": config_status,
        "config_path": config_path,
        "ajo_version": ajo_version,
    }


def _detect_environment_name() -> str:
    """Detect the Python environment name using ``ajo.core.environment``."""
    try:
        from ajo.core.environment import detect_environment, environment_display  # noqa: PLC0415

        env = detect_environment()
        return environment_display(env)
    except Exception:
        return "unknown"


def _check_config_status() -> tuple[str, str | None]:
    """Check whether ajo's config file exists and is loadable."""
    try:
        from ajo.core.config import CONFIG_FILE, ConfigManager  # noqa: PLC0415

        path = str(CONFIG_FILE)
        if CONFIG_FILE.is_file():
            ConfigManager()  # triggers load; logs on error but never raises
            return "✓ Found", path
        return "— Not created", path
    except Exception:
        return "⚠ Error", None


def _detect_django_version(project_root: Path) -> str:
    """Detect the installed Django version via a lightweight subprocess call.

    Args:
        project_root: The Django project root (used as CWD for the subprocess
            so that the correct virtualenv's Django is found).

    Returns:
        A version string (e.g. ``"5.1.3"``) or ``"N/A"`` on failure.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import django; print(django.get_version())"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            if version:
                return version
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.debug("Django version detection failed", exc_info=True)
    return "N/A"


def _count_middleware(settings_path: Path) -> int:
    """Count entries in the ``MIDDLEWARE`` list from a ``settings.py`` file.

    Args:
        settings_path: Path to the Django ``settings.py``.

    Returns:
        The number of middleware entries, or ``0`` if the file is
        inaccessible or the list cannot be parsed.
    """
    try:
        if not settings_path.is_file():
            return 0
        text = settings_path.read_text(encoding="utf-8")

        # Find MIDDLEWARE list content between brackets
        match = re.search(
            r"^MIDDLEWARE\s*=\s*\[(.*?)\]",
            text,
            re.DOTALL | re.MULTILINE,
        )
        if not match:
            return 0

        body = match.group(1)
        # Count non-empty, non-comment lines
        count = 0
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
        return count
    except (OSError, PermissionError):
        return 0


def _count_url_patterns(urls_path: Path) -> int:
    """Count ``path(`` / ``re_path(`` / ``include(`` calls in ``urls.py``.

    Args:
        urls_path: Path to the Django ``urls.py``.

    Returns:
        The number of URL pattern entries, or ``0`` if the file is
        inaccessible.
    """
    try:
        if not urls_path.is_file():
            return 0
        text = urls_path.read_text(encoding="utf-8")

        # Count top-level route-registration calls.
        # ``include()`` and ``url()`` are legacy/nested — only count
        # ``path()`` and ``re_path()`` which register actual routes.
        patterns = re.findall(
            r"\b(path|re_path)\s*\(",
            text,
        )
        return len(patterns)
    except (OSError, PermissionError):
        return 0


def _create_detector() -> Any | None:
    """Create and return a ``DjangoProjectDetector`` instance.

    Returns ``None`` if the detector module is not available.
    """
    try:
        from ajo.detector.project import DjangoProjectDetector  # noqa: PLC0415

        return DjangoProjectDetector()
    except Exception:
        return None


# ── Rendering ──────────────────────────────────────────────────────────────


def _render_health_card(data: dict[str, Any]) -> None:
    """Display the health card using Rich (with plain-text fallback).

    Args:
        data: The scan data dictionary from :func:`_gather_scan_data`.
    """
    console = _get_console()
    if console is None:
        _render_plain(data)
        return

    if not data.get("is_django_project"):
        console.print(_non_django_message(data))
        return

    # Build the health card
    from rich.panel import Panel  # noqa: PLC0415
    from rich.table import Table  # noqa: PLC0415

    # ── Header ──────────────────────────────────────────────────────────
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold cyan", no_wrap=True)
    header.add_column(style="white")
    header.add_row("Project:", data.get("project_name", "Unknown"))
    header.add_row("Path:", data.get("path", "N/A"))
    header.add_row("Django:", data.get("django_version", "N/A"))
    header.add_row("Python Env:", data.get("environment", "unknown"))
    header.add_row("Config:", f"{data.get('config_status', 'N/A')}")
    header.add_row("ajo:", f"v{data.get('ajo_version', 'N/A')}")

    # ── Metrics ─────────────────────────────────────────────────────────
    metrics = Table.grid(padding=(0, 1))
    metrics.add_column(style="dim", width=20)
    metrics.add_column(style="bold yellow", justify="right")

    metrics.add_row("Models", str(data.get("models_count", 0)))
    metrics.add_row("Installed Apps", str(data.get("apps_count", 0)))
    metrics.add_row("Middleware", str(data.get("middleware_count", 0)))
    metrics.add_row("URL Patterns", str(data.get("url_patterns_count", 0)))

    if data.get("git_branch") and data["git_branch"] != "N/A":
        metrics.add_row("Git Branch", data["git_branch"])

    # ── Feature flags ───────────────────────────────────────────────────
    flags = []
    if data.get("has_admin"):
        flags.append("[green]✓ Admin[/]")
    else:
        flags.append("[dim]— Admin[/]")
    if data.get("venv_active"):
        flags.append("[green]✓ Virtualenv[/]")
    else:
        flags.append("[dim]— Virtualenv[/]")
    if data.get("server_running"):
        flags.append("[yellow]⚡ Dev Server[/]")
    if data.get("has_static"):
        flags.append("[green]✓ Static[/]")
    if data.get("has_media"):
        flags.append("[green]✓ Media[/]")

    # ── Installed Apps list ─────────────────────────────────────────────
    apps = data.get("apps", [])
    apps_display = ", ".join(apps[:8])
    if len(apps) > 8:
        apps_display += f" [dim](+{len(apps) - 8} more)[/]"

    # ── Combine into a Table ────────────────────────────────────────────
    table = Table.grid(padding=(0, 2))
    table.add_column(ratio=1)
    table.add_column(ratio=1)

    table.add_row(header, metrics)
    if flags:
        table.add_row(f"[bold]Features:[/] {'  '.join(flags)}", "")
    table.add_row(f"[bold]Apps ({data.get('apps_count', 0)}):[/]", apps_display)

    card = Panel(
        table,
        title="[bold cyan]🏥 Project Health Card[/]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(card)


def _non_django_message(data: dict[str, Any]) -> Panel:
    """Return a Rich Panel explaining that no Django project was found."""
    from rich.panel import Panel  # noqa: PLC0415

    text = (
        f"[yellow]No Django project detected[/] in:\n"
        f"  [dim]{data.get('path', 'N/A')}[/]\n\n"
        f"Run [bold]ajo scan[/] from a Django project root (where "
        f"[bold]manage.py[/] lives) to see its health card."
    )
    return Panel(text, title="[bold]ajo scan[/]", border_style="yellow")


def _render_plain(data: dict[str, Any]) -> None:
    """Plain-text fallback when Rich is unavailable."""
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append("PROJECT HEALTH CARD")
    lines.append("=" * 50)
    lines.append(f"Project:  {data.get('project_name', 'N/A')}")
    lines.append(f"Path:     {data.get('path', 'N/A')}")
    lines.append(f"Django:   {data.get('django_version', 'N/A')}")
    lines.append(f"Python:   {data.get('environment', 'unknown')}")
    lines.append(f"Config:   {data.get('config_status', 'N/A')}")
    lines.append(f"ajo:      v{data.get('ajo_version', 'N/A')}")
    lines.append("")
    lines.append(f"Models:       {data.get('models_count', 0)}")
    lines.append(f"Apps:         {data.get('apps_count', 0)}")
    lines.append(f"Middleware:   {data.get('middleware_count', 0)}")
    lines.append(f"URL Patterns: {data.get('url_patterns_count', 0)}")
    lines.append("")
    if data.get("apps"):
        lines.append(f"Installed: {', '.join(data['apps'])}")
    lines.append("=" * 50)
    sys.stdout.write("\n".join(lines) + "\n")


def _render_json(data: dict[str, Any]) -> None:
    """Output scan data as JSON."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _get_console():
    """Return a Rich Console or None if unavailable."""
    try:
        from rich.console import Console as RichConsole  # noqa: PLC0415

        return RichConsole()
    except ImportError:
        return None
