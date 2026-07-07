"""Tests for ajo.commands.changelog.

All network-bound functions mock ``urllib.request`` so no real HTTP
requests are made during testing.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ajo.commands.changelog import (
    _extract_latest_entry,
    _fetch_github_releases,
    _resolve_local_changelog,
    run,
)


# ═════════════════════════════════════════════════════════════════════════════
# Sample data
# ═════════════════════════════════════════════════════════════════════════════

SAMPLE_CHANGELOG = """# Changelog

## 3.3.0 (2026-07-01)

### Added
- Cyberpunk TUI theme engine
- Interactive project scaffolding

### Fixed
- Color support detection on legacy terminals

## 3.2.0 (2026-06-15)

### Added
- Initial project scaffolding support
- Basic configuration management

### Fixed
- Python 3.10 compatibility issues
"""

SAMPLE_SINGLE_ENTRY = """## 3.3.0 (2026-07-01)

### Added
- Cyberpunk TUI theme engine
- Interactive project scaffolding
"""


# ═════════════════════════════════════════════════════════════════════════════
# _extract_latest_entry
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractLatestEntry:
    def test_extracts_first_entry(self) -> None:
        result = _extract_latest_entry(SAMPLE_CHANGELOG)
        assert "3.3.0" in result
        assert "3.2.0" not in result
        assert result.endswith("\n")

    def test_single_entry(self) -> None:
        result = _extract_latest_entry(SAMPLE_SINGLE_ENTRY)
        assert "3.3.0" in result
        assert result == SAMPLE_SINGLE_ENTRY

    def test_no_headings(self) -> None:
        text = "Some plain text\nwithout any headings\n"
        result = _extract_latest_entry(text)
        assert result == text

    def test_empty_string(self) -> None:
        assert _extract_latest_entry("") == ""

    def test_skips_document_title(self) -> None:
        """``# Changelog`` title is skipped — first ``##`` is the entry."""
        md = "# Changelog\n\n## 3.3.0\n\nContent A\n\n## 3.2.0\n\nContent B\n"
        result = _extract_latest_entry(md)
        assert "3.3.0" in result
        assert "3.2.0" not in result
        assert "Content A" in result
        assert "Changelog" not in result


# ═════════════════════════════════════════════════════════════════════════════
# _resolve_local_changelog
# ═════════════════════════════════════════════════════════════════════════════


class TestResolveLocalChangelog:
    def test_finds_existing_file(self, tmp_path: Path) -> None:
        """Reads content from a CHANGELOG.md in the first candidate dir."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")

        with patch(
            "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
            (changelog,),
        ):
            result = _resolve_local_changelog()
            assert result == SAMPLE_CHANGELOG

    def test_returns_none_when_missing(self) -> None:
        """No file in any candidate path → None."""
        with patch(
            "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
            (Path("/nonexistent/CHANGELOG.md"),),
        ):
            result = _resolve_local_changelog()
            assert result is None

    def test_latest_only(self, tmp_path: Path) -> None:
        """only_latest=True returns only the first entry."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")

        with patch(
            "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
            (changelog,),
        ):
            result = _resolve_local_changelog(only_latest=True)
            assert result is not None
            assert "3.3.0" in result
            assert "3.2.0" not in result


# ═════════════════════════════════════════════════════════════════════════════
# _fetch_github_releases
# ═════════════════════════════════════════════════════════════════════════════


def _mock_release(
    tag: str = "v3.3.0",
    name: str = "v3.3.0",
    body: str = "Release notes body",
    published: str = "2026-07-07T00:00:00Z",
) -> dict:
    return {
        "tag_name": tag,
        "name": name,
        "body": body,
        "published_at": published,
    }


class TestFetchGitHubReleases:
    def test_returns_formatted_markdown(self) -> None:
        """Successful API response returns formatted markdown."""
        releases = [_mock_release()]
        payload = json.dumps(releases).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = _fetch_github_releases()

        assert result is not None
        assert "v3.3.0" in result
        assert "Release notes body" in result
        assert "2026-07-07" in result

    def test_only_latest(self) -> None:
        """only_latest=True only fetches most recent release."""
        releases = [_mock_release()]
        payload = json.dumps(releases).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = _fetch_github_releases(only_latest=True)

        assert result is not None
        # Verify URL includes per_page=1
        called_url = mock_urlopen.call_args[0][0].full_url
        assert "per_page=1" in called_url

    def test_includes_token_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GitHub token is sent as Authorization header when env var set."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
        releases = [_mock_release()]
        payload = json.dumps(releases).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            _fetch_github_releases()

        called_headers = mock_urlopen.call_args[0][0].headers
        assert called_headers.get("Authorization") == "Bearer ghp_fake"

    def test_network_error_returns_none(self) -> None:
        """URLError → graceful None."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("fail")
            result = _fetch_github_releases()
            assert result is None

    def test_empty_response_returns_none(self) -> None:
        """Empty JSON array → graceful None."""
        payload = json.dumps([]).encode("utf-8")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = _fetch_github_releases()
            assert result is None

    def test_release_with_empty_body(self) -> None:
        """Release with empty body is skipped."""
        releases = [_mock_release(body="")]
        payload = json.dumps(releases).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = _fetch_github_releases()
            assert result is None  # No releases with content

    def test_multiple_releases(self) -> None:
        """Multiple releases are concatenated."""
        releases = [
            _mock_release(tag="v3.3.0", body="Release A"),
            _mock_release(tag="v3.2.0", body="Release B"),
        ]
        payload = json.dumps(releases).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = _fetch_github_releases()
        assert result is not None
        assert "Release A" in result
        assert "Release B" in result


# ═════════════════════════════════════════════════════════════════════════════
# run (integration with mocked sources)
# ═════════════════════════════════════════════════════════════════════════════


class MockArgs:
    """Minimal argparse.Namespace stand-in."""

    def __init__(self, latest: bool = False) -> None:
        self.latest = latest


class TestRun:
    def test_local_changelog_success(self, tmp_path: Path) -> None:
        """run() returns 0 when local changelog is found."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")

        with patch(
            "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
            (changelog,),
        ):
            result = run(MockArgs(latest=False))

        assert result == 0

    def test_local_changelog_latest(self, tmp_path: Path) -> None:
        """run() with --latest shows only first entry."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")

        with patch(
            "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
            (changelog,),
        ):
            result = run(MockArgs(latest=True))

        assert result == 0

    def test_falls_back_to_github(self) -> None:
        """When no local file exists, falls back to GitHub API."""
        releases = [_mock_release(body="GitHub release content")]
        payload = json.dumps(releases).encode("utf-8")

        with (
            patch(
                "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
                (Path("/nonexistent/CHANGELOG.md"),),
            ),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = run(MockArgs(latest=False))

        assert result == 0

    def test_both_sources_fail_returns_1(self) -> None:
        """Returns 1 when both local file and GitHub are unavailable."""
        with (
            patch(
                "ajo.commands.changelog.LOCAL_CHANGELOG_PATHS",
                (Path("/nonexistent/CHANGELOG.md"),),
            ),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_urlopen.side_effect = urllib.error.URLError("fail")
            result = run(MockArgs(latest=False))

        assert result == 1
