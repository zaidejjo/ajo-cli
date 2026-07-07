"""Tests for ajo.core.typo_correction."""

from __future__ import annotations

import sys
from io import StringIO
from unittest import mock

import pytest

from ajo.core.typo_correction import (
    SUGGESTION_CUTOFF,
    _get_subcommand_names,
    check_and_suggest,
    format_suggestion,
    suggest_command,
)


# =============================================================================
# suggest_command
# =============================================================================


class TestSuggestCommand:
    """Tests for the core fuzzy-matching logic."""

    CANDIDATES = ["doctor", "completion", "scaffold", "diagnostics", "upgrade"]

    def test_exact_match(self) -> None:
        """An exact match returns the candidate."""
        assert suggest_command("doctor", self.CANDIDATES) == "doctor"

    def test_close_match(self) -> None:
        """A one-character typo returns the closest candidate."""
        assert suggest_command("doctir", self.CANDIDATES) == "doctor"
        assert suggest_command("scafold", self.CANDIDATES) == "scaffold"

    def test_transposition(self) -> None:
        """Transposed letters are still matched."""
        assert suggest_command("coompletion", self.CANDIDATES) == "completion"

    def test_no_match(self) -> None:
        """Completely unrelated input returns None."""
        assert suggest_command("xyzzy", self.CANDIDATES) is None

    def test_empty_string(self) -> None:
        """Empty string returns None."""
        assert suggest_command("", self.CANDIDATES) is None

    def test_empty_candidates(self) -> None:
        """Empty candidates list returns None."""
        assert suggest_command("doctor", []) is None

    def test_cutoff_filter(self) -> None:
        """Strings below SUGGESTION_CUTOFF similarity are rejected."""
        # "qux" is very dissimilar to any candidate
        assert suggest_command("qux", self.CANDIDATES) is None

    def test_short_candidate_still_matches(self) -> None:
        """Short candidate names are still matched if similarity is high enough."""
        assert suggest_command("doc", ["doctor", "completion"]) == "doctor"


# =============================================================================
# format_suggestion
# =============================================================================


class TestFormatSuggestion:
    """Tests for the user-facing message formatter."""

    def test_basic_format(self) -> None:
        msg = format_suggestion("scafold", "scaffold")
        assert msg == 'Did you mean "scaffold"? (not "scafold")'

    def test_contains_bad_and_good(self) -> None:
        msg = format_suggestion("doctr", "doctor")
        assert "doctor" in msg
        assert "doctr" in msg

    def test_no_ansi_codes(self) -> None:
        """The message must be plain text (no Rich markup or ANSI escapes)."""
        msg = format_suggestion("bad", "good")
        assert "\x1b[" not in msg
        assert "[" not in msg or msg.index("[") > msg.index('"')
        # The only "[" should be inside quotes or similar


# =============================================================================
# _get_subcommand_names
# =============================================================================


class TestGetSubcommandNames:
    """Tests for extracting subcommand names from an ArgumentParser."""

    def test_returns_registered_subcommands(self) -> None:
        import argparse

        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest="command")
        subs.add_parser("doctor")
        subs.add_parser("completion")

        names = _get_subcommand_names(parser)
        assert sorted(names) == ["completion", "doctor"]

    def test_no_subparsers_returns_empty(self) -> None:
        import argparse

        parser = argparse.ArgumentParser()
        assert _get_subcommand_names(parser) == []

    def test_ajo_parser(self) -> None:
        """Verify against the real ajo parser."""
        from ajo.cli import build_parser

        parser = build_parser()
        names = _get_subcommand_names(parser)
        assert "doctor" in names
        assert "completion" in names


# =============================================================================
# check_and_suggest
# =============================================================================


class TestCheckAndSuggest:
    """Tests for the convenience wrapper."""

    def test_suggests_on_unknown_subcommand(self) -> None:
        from ajo.cli import build_parser

        parser = build_parser()
        buf = StringIO()
        result = check_and_suggest("docotr", parser, file=buf)
        assert result is True
        output = buf.getvalue()
        assert "doctor" in output
        assert "docotr" in output

    def test_returns_false_for_known_flags(self) -> None:
        from ajo.cli import build_parser

        parser = build_parser()
        buf = StringIO()
        result = check_and_suggest("--version", parser, file=buf)
        assert result is False
        assert buf.getvalue() == ""

    def test_returns_false_for_garbage(self) -> None:
        from ajo.cli import build_parser

        parser = build_parser()
        buf = StringIO()
        result = check_and_suggest("xyzzynonsense", parser, file=buf)
        assert result is False
        assert buf.getvalue() == ""
