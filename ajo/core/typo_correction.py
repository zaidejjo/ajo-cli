"""Fuzzy typo correction for mistyped CLI subcommands.

Uses :func:`difflib.get_close_matches` (stdlib, zero dependencies) to suggest
a correction when a user types an unknown subcommand::

    $ ajo scafold
    Did you mean "scaffold"? (not "scafold")
"""

from __future__ import annotations

import difflib
import sys
from typing import IO

#: Minimum similarity ratio (0.0 – 1.0) for a suggestion to be considered.
#: Lower values permit more distant matches; higher values require closer ones.
SUGGESTION_CUTOFF: float = 0.4


def suggest_command(bad: str, candidates: list[str]) -> str | None:
    """Return the closest match among *candidates*, or ``None``.

    Uses :func:`difflib.get_close_matches` with :data:`SUGGESTION_CUTOFF`.
    Only the single best match (if any) is returned.

    Args:
        bad: The mistyped command the user entered.
        candidates: The list of known valid subcommand names.

    Returns:
        The closest matching command name, or ``None`` if nothing is close
        enough.
    """
    matches = difflib.get_close_matches(bad, candidates, n=1, cutoff=SUGGESTION_CUTOFF)
    return matches[0] if matches else None


def format_suggestion(bad: str, good: str) -> str:
    """Return a user-facing suggestion message.

    The message is plain text (no ANSI codes) suitable for ``stderr``::

        Did you mean "<good>"? (not "<bad>")

    Args:
        bad: The mistyped command the user entered.
        good: The suggested correct command.

    Returns:
        A formatted suggestion string.
    """
    return f'Did you mean "{good}"? (not "{bad}")'


def _get_subcommand_names(parser: object) -> list[str]:
    """Extract registered subcommand names from an ``ArgumentParser``.

    Iterates over the parser's internal ``_actions`` list looking for a
    ``_SubParsersAction`` (the type created by ``add_subparsers()``).
    This is a well-known argparse private API, stable since Python 3.x.

    Args:
        parser: An ``argparse.ArgumentParser`` instance.

    Returns:
        A list of subcommand name strings (e.g. ``["doctor", "completion"]``).
        Empty if no subparsers have been registered.
    """
    import argparse

    for action in getattr(parser, "_actions", []):
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices.keys())
    return []


def check_and_suggest(
    bad: str,
    parser: object,
    *,
    file: IO[str] = sys.stderr,
) -> bool:
    """Check if *bad* resembles a known subcommand and, if so, print a suggestion.

    This is a convenience wrapper that combines :func:`_get_subcommand_names`,
    :func:`suggest_command`, and :func:`format_suggestion` for the common case.

    Args:
        bad: The unknown token the user typed.
        parser: An ``argparse.ArgumentParser`` instance.
        file: Output stream (defaults to ``sys.stderr``).

    Returns:
        ``True`` if a suggestion was printed, ``False`` otherwise.
    """
    # Only attempt correction for bare words, not flags
    if bad.startswith("-"):
        return False

    candidates = _get_subcommand_names(parser)
    if not candidates:
        return False

    suggestion = suggest_command(bad, candidates)
    if suggestion is None:
        return False

    print(format_suggestion(bad, suggestion), file=file)
    return True
