"""``ajo upgrade`` — Self-update command.

Uses :mod:`ajo.core.updater` to check PyPI for the latest version, then
runs the correct upgrade command for the current Python environment
(``uv tool upgrade``, ``pipx upgrade``, or ``pip install --upgrade``)
via :func:`ajo.core.environment.upgrade_command`.

Usage::

    ajo upgrade           # Check and upgrade if newer
    ajo upgrade --check   # Only check, don't upgrade
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from ajo import __version__
from ajo.core.updater import check_for_updates, format_update_message


def run(args: Any) -> int:
    """Execute the ``ajo upgrade`` subcommand.

    Args:
        args: The parsed ``argparse.Namespace`` from the CLI parser.

    Returns:
        Exit code: 0 = success, 1 = error.
    """
    # 1. Check for updates (force — always hit PyPI for the upgrade command)
    import logging

    logging.getLogger("ajo.core.updater").setLevel(logging.WARNING)
    result = check_for_updates(force=True)

    if result is None:
        # Could not reach PyPI
        print(
            "[bold yellow]Could not check for updates.[/] "
            "[dim]PyPI may be unreachable.[/]",
            file=sys.stderr,
        )
        if not getattr(args, "check", False):
            return 1
        return 0

    latest, is_newer = result

    if not is_newer:
        print(f"[green]✓ You're up to date[/] [dim](v{__version__})[/]")
        return 0

    # 2. Show what's available
    print(format_update_message(latest))
    print()

    # 3. If --check only, stop here
    if getattr(args, "check", False):
        return 0

    # 4. Confirm?
    if not getattr(args, "yes", False):
        try:
            response = input("  Proceed with upgrade? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if response not in ("", "y", "yes"):
            print("  Upgrade cancelled.")
            return 0

    # 5. Run the upgrade command
    from ajo.core.environment import upgrade_command

    cmd = upgrade_command()
    print(f"  Running: [dim]{' '.join(cmd)}[/]")
    print()

    # Use Rich's Console if available, otherwise raw print
    try:
        # Try importing the configured console for styled output
        from ajo.core.color_control import configure_console as _cc

        upgrade_console = _cc()
    except Exception:
        upgrade_console = None

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
            if upgrade_console:
                upgrade_console.print(f"[bold red]Upgrade failed:[/] {error_msg}")
            else:
                print(f"Upgrade failed: {error_msg}", file=sys.stderr)
            return 1

        if upgrade_console:
            upgrade_console.print(
                f"[bold green]✓ Upgrade complete![/] "
                f"[dim]You're now running the latest version.[/]"
            )
        else:
            print("Upgrade complete!")

        return 0

    except subprocess.TimeoutExpired:
        if upgrade_console:
            upgrade_console.print("[bold red]Upgrade timed out after 120 seconds.[/]")
        else:
            print("Upgrade timed out after 120 seconds.", file=sys.stderr)
        return 1

    except FileNotFoundError:
        executable = cmd[0]
        if upgrade_console:
            upgrade_console.print(
                f"[bold red]Executable not found:[/] {executable}\n"
                f"[dim]Make sure {executable} is installed and on your PATH.[/]"
            )
        else:
            print(f"Executable not found: {executable}", file=sys.stderr)
        return 1
