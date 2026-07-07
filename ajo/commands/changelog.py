"""``ajo changelog`` — Display the project changelog.

Reads the local ``CHANGELOG.md`` if available in the current directory or
the package root; otherwise fetches the latest release notes from the
GitHub Releases API (``/repos/zaidejjo/ajo-cli/releases``).

Usage::

    ajo changelog           # Show full history (local; fallback to GitHub)
    ajo changelog --latest  # Show only the most recent entry / release
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ajo import __version__

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

GITHUB_API_URL: str = "https://api.github.com/repos/zaidejjo/ajo-cli/releases"

#: HTTP request timeout in seconds.
REQUEST_TIMEOUT: int = 10

#: Environment variable for an optional GitHub token (higher API rate limit).
GITHUB_TOKEN_ENV: str = "GITHUB_TOKEN"

#: Candidate locations for a local changelog file, checked in order.
LOCAL_CHANGELOG_PATHS: tuple[Path, ...] = (
    Path.cwd() / "CHANGELOG.md",
    Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md",
)


# ── Public entry point ─────────────────────────────────────────────────────


def run(args: Any) -> int:
    """Execute the ``ajo changelog`` subcommand.

    Resolution order:
        1. Local ``CHANGELOG.md`` (current directory, then package root).
        2. GitHub Releases API (latest releases).
        3. Error message if both sources are unavailable.

    Args:
        args: Parsed ``argparse.Namespace``.

    Returns:
        Exit code: 0 = success, 1 = error.
    """
    only_latest = getattr(args, "latest", False)

    # 1. Try local CHANGELOG.md
    content = _resolve_local_changelog(only_latest=only_latest)

    # 2. Fall back to GitHub Releases API
    if content is None:
        content = _fetch_github_releases(only_latest=only_latest)

    # 3. Render or error
    if content is None:
        _error("No changelog found locally and unable to fetch from GitHub.")
        return 1

    _render_changelog(content, latest_only=only_latest)
    return 0


# ── Local file resolution ──────────────────────────────────────────────────


def _resolve_local_changelog(*, only_latest: bool = False) -> str | None:
    """Search candidate paths for ``CHANGELOG.md`` and return its content.

    Args:
        only_latest: If ``True``, return only the first version entry.

    Returns:
        The raw markdown content (or the first-entry subset), or ``None``
        if no local changelog file exists.
    """
    for path in LOCAL_CHANGELOG_PATHS:
        try:
            if path.is_file():
                raw = path.read_text(encoding="utf-8")
                if only_latest:
                    return _extract_latest_entry(raw)
                return raw
        except (OSError, PermissionError):
            continue
    return None


# ── GitHub Releases API ────────────────────────────────────────────────────


def _fetch_github_releases(*, only_latest: bool = False) -> str | None:
    """Fetch the latest release notes from the GitHub Releases API.

    Args:
        only_latest: If ``True``, fetch only the most recent release.

    Returns:
        Formatted markdown string, or ``None`` on failure.
    """
    per_page = 1 if only_latest else 5
    url = f"{GITHUB_API_URL}?per_page={per_page}"

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"ajo-cli/{__version__}",
    }

    token = os.environ.get(GITHUB_TOKEN_ENV, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data: list[dict[str, Any]] = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.debug("GitHub releases fetch failed: %s", exc)
        return None

    if not data:
        logger.debug("GitHub releases API returned empty list")
        return None

    # Build markdown from release entries
    parts: list[str] = []
    for release in data:
        tag = release.get("tag_name", "")
        name = release.get("name", "") or tag
        body = (release.get("body") or "").strip()
        published = (release.get("published_at") or "")[:10]  # "2026-07-07"

        if body:
            header = f"## {name} ({tag}) — {published}"
            parts.append(f"{header}\n\n{body}\n")

    return "\n".join(parts) if parts else None


# ── Markdown helpers ───────────────────────────────────────────────────────


def _extract_latest_entry(markdown: str) -> str:
    """Extract the first version entry from a changelog markdown string.

    An entry is everything from the first level-2 heading (``## ``)
    until the next level-1 or level-2 heading, or the end of the string.
    Leading document-title headings (``# ``) are skipped so that
    ``# Changelog`` above ``## 3.3.0`` doesn't consume everything.

    Args:
        markdown: The full changelog markdown.

    Returns:
        The first version entry as raw markdown, or the full input if no
        version heading could be found.
    """
    # Find the first level-2 heading — this is the start of a version entry
    match = re.search(r"^##\s", markdown, re.MULTILINE)
    if not match:
        return markdown  # No version headings — return as-is

    start = match.start()
    rest = markdown[match.end() :]

    # Find the next level-1 or level-2 heading (end of this entry)
    next_match = re.search(r"^#{1,2}\s", rest, re.MULTILINE)
    if next_match:
        end = match.end() + next_match.start()
        return markdown[start:end].rstrip() + "\n"
    else:
        return markdown[start:].rstrip() + "\n"


# ── Rendering ──────────────────────────────────────────────────────────────


def _render_changelog(content: str, *, latest_only: bool = False) -> None:
    """Display the changelog content using Rich.

    Falls back to plain ``print()`` if Rich is unavailable.

    Args:
        content: The raw markdown content to render.
        latest_only: Whether this is a ``--latest`` view.
    """
    # Try to use Rich for formatted output
    console = _get_console()
    if console is None:
        # Fallback: plain print
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
        return

    title = (
        "[bold cyan]Changelog — Latest[/]" if latest_only else "[bold cyan]Changelog[/]"
    )

    try:
        from rich.markdown import Markdown  # noqa: PLC0415
        from rich.panel import Panel  # noqa: PLC0415

        md = Markdown(content)
        panel = Panel(md, title=title, border_style="cyan")
        console.print(panel)
    except ImportError:
        # Rich but no Markdown/Panel (shouldn't happen with modern rich)
        console.print(title)
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")


def _get_console():
    """Return a Rich Console or None if unavailable."""
    try:
        from rich.console import Console as RichConsole  # noqa: PLC0415

        return RichConsole()
    except ImportError:
        return None


def _error(message: str) -> None:
    """Print an error message, using Rich if possible."""
    console = _get_console()
    if console:
        console.print(f"[bold red]Error:[/] {message}")
    else:
        print(f"Error: {message}", file=sys.stderr)
