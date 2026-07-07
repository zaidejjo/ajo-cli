"""``ajo completion <shell>`` — Generate shell-completion scripts.

Wraps ``shtab`` to produce completion files for bash, zsh, and tcsh
directly from the argparse definition — zero manual maintenance.

Usage::

    ajo completion bash   > /etc/bash_completion.d/ajo
    ajo completion zsh    > /usr/local/share/zsh/site-functions/_ajo
    ajo completion tcsh   > /etc/csh/completions/ajo.csh
"""

from __future__ import annotations

import sys
from typing import Any


def run(args: Any) -> int:
    """Generate and print a shell-completion script.

    Args:
        args: Parsed ``argparse.Namespace`` with ``.shell`` set to
              ``"bash"``, ``"zsh"``, or ``"tcsh"``.

    Returns:
        ``0`` on success, ``1`` if ``shtab`` is not installed.
    """
    try:
        import shtab  # noqa: PLC0415 — optional dependency
    except ImportError:
        print(
            "Error: shtab is required for shell completions.\n"
            "Install it with: pip install shtab  (or: uv add shtab)",
            file=sys.stderr,
        )
        return 1

    # Lazy import to avoid circular dependency at module level
    from ajo.cli import build_parser  # noqa: PLC0415

    parser = build_parser()

    try:
        completion_script = shtab.complete(parser, shell=args.shell)
    except (ValueError, NotImplementedError) as exc:
        print(
            f"Error generating completions for '{args.shell}': {exc}", file=sys.stderr
        )
        return 1

    print(completion_script)
    return 0
