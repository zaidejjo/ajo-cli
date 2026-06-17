"""AJO - Professional Django Scaffolder."""

from __future__ import annotations

import sys as _sys
from pathlib import Path


# ── Read version dynamically from pyproject.toml ─────────────────────────
def _get_version() -> str:
    try:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "3.3.0"  # Fallback version


__version__ = _get_version()
__author__ = "Zaid Ajo"
__license__ = "MIT"


# ── Fast-path dispatch for --version (under 50ms) ────────────────────────
# Both ``ajo --version`` (console_scripts entry point) and
# ``python -m ajo`` (__main__.py) go through here.  The version check
# avoids importing ``ajo.cli`` (and hence Rich, InquirerPy, etc.)
# for the version query.

if "--version" in _sys.argv:  # noqa: SIM115  -- intentional early check
    print(f"ajo v{__version__}")
    _sys.exit(0)


def main() -> int:
    """Lazy-loading CLI entry point.

    ``from ajo import main`` does **not** import ``ajo.cli`` (and hence
    does **not** load Rich, InquirerPy, or their transitive dependencies).
    The heavy import happens only when ``main()`` is actually called.
    """
    from ajo.cli import main as _cli_main  # noqa: PLC0415  -- intentional

    return _cli_main()


__all__ = ["main", "__version__", "__author__", "__license__"]
