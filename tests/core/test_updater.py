"""Tests for ajo.core.updater.

All network-bound functions mock ``urllib.request`` so no real HTTP
requests are made during testing.
"""

from __future__ import annotations

import json
import threading
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from ajo import __version__
from ajo.core.updater import (
    CACHE_FILE,
    NO_UPDATE_CHECK_ENV,
    _background_check,
    _read_cache,
    _write_cache,
    check_for_updates,
    check_in_background,
    format_update_message,
    get_cached_update,
    parse_version,
    should_check_updates,
)

import ajo.core.updater as _updater_mod  # for accessing module-level _cache


# ── Module-level fixture: isolate shared state per test ────────────────────


@pytest.fixture(autouse=True)
def _reset_updater_state() -> None:
    """Reset in-memory *and* on-disk cache before every test in this module.

    Without this fixture, tests leak state through the module-level
    ``updater._cache`` dict and the ``~/.config/ajo/update_cache.json``
    file, causing spurious failures when running the full suite.
    """
    # Reset in-memory cache
    import ajo.core.updater as _updater_mod

    _updater_mod._cache = None  # noqa: SLF001

    # Remove on-disk cache file (if any)
    if CACHE_FILE.is_file():
        CACHE_FILE.unlink()


# =============================================================================
# parse_version
# =============================================================================


class TestParseVersion:
    def test_simple(self) -> None:
        assert parse_version("3.3.0") == (3, 3, 0)

    def test_major_minor(self) -> None:
        assert parse_version("3.3") == (3, 3)

    def test_three_parts(self) -> None:
        assert parse_version("1.0.0") == (1, 0, 0)

    def test_pre_release(self) -> None:
        """Non-numeric suffixes are ignored."""
        assert parse_version("3.3.0rc1") == (3, 3, 0)

    def test_dev_release(self) -> None:
        assert parse_version("3.4.0.dev123") == (3, 4, 0)

    def test_comparison(self) -> None:
        assert parse_version("3.4.0") > parse_version("3.3.0")
        assert parse_version("3.3.1") > parse_version("3.3.0")
        assert parse_version("3.3.0") == parse_version("3.3.0")


# =============================================================================
# should_check_updates
# =============================================================================


class TestShouldCheckUpdates:
    def test_default_true(self) -> None:
        """No env var, no config → True."""
        assert should_check_updates(config={}) is True

    def test_default_no_config(self) -> None:
        """No config at all (None) → True."""
        assert should_check_updates(config=None) is True

    def test_env_var_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "1")
        assert should_check_updates(config={}) is False

    def test_env_var_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "true")
        assert should_check_updates(config={}) is False

    def test_env_var_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "yes")
        assert should_check_updates(config={}) is False

    def test_env_var_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "True")
        assert should_check_updates(config={}) is False

    def test_env_var_not_set(self) -> None:
        """Unset or irrelevant value → True."""
        assert should_check_updates(config={}) is True

    def test_config_false(self) -> None:
        """Config check_updates=False → False (no env var)."""
        assert should_check_updates(config={"check_updates": False}) is False

    def test_config_true(self) -> None:
        assert should_check_updates(config={"check_updates": True}) is True

    def test_env_overrides_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var takes precedence over config."""
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "1")
        assert should_check_updates(config={"check_updates": True}) is False


# =============================================================================
# check_for_updates
# =============================================================================


def _mock_pypi_response(latest_version: str) -> bytes:
    """Return a fake PyPI JSON API response body."""
    return json.dumps({"info": {"version": latest_version}}).encode("utf-8")


class TestCheckForUpdates:
    def test_newer_version_available(self) -> None:
        """Returns (latest_version, True) when PyPI has a newer version."""
        fake_body = _mock_pypi_response("9.9.9")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = check_for_updates(force=True)

        assert result is not None
        latest, is_newer = result
        assert latest == "9.9.9"
        assert is_newer is True

    def test_same_version(self) -> None:
        """Returns (version, False) when running the latest."""
        fake_body = _mock_pypi_response(__version__)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = check_for_updates(force=True)

        assert result is not None
        latest, is_newer = result
        assert latest == __version__
        assert is_newer is False

    def test_network_error(self) -> None:
        """Returns None on URLError."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("fail")

            result = check_for_updates(force=True)

        assert result is None

    def test_suppressed_by_env_non_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns None when AJO_NO_UPDATE_CHECK is set and force=False."""
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "1")
        result = check_for_updates(force=False)
        assert result is None

    def test_suppressed_by_config_non_force(self) -> None:
        """Returns None when check_updates=False in config and force=False."""
        result = check_for_updates(force=False, config={"check_updates": False})
        assert result is None

    def test_force_bypasses_env_suppression(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """force=True ignores AJO_NO_UPDATE_CHECK (user explicitly asked)."""
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "1")
        fake_body = _mock_pypi_response("9.9.9")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = check_for_updates(force=True)

        assert result is not None
        latest, is_newer = result
        assert latest == "9.9.9"
        assert is_newer is True

    def test_force_bypasses_config_suppression(self) -> None:
        """force=True ignores check_updates=False config (user explicitly asked)."""
        fake_body = _mock_pypi_response("9.9.9")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = check_for_updates(force=True, config={"check_updates": False})

        assert result is not None
        latest, is_newer = result
        assert latest == "9.9.9"
        assert is_newer is True

    def test_force_bypasses_cache(self) -> None:
        """force=True still fires even if disk cache is fresh."""
        stale_entry = {
            "latest_version": "0.0.1",
            "current_version": __version__,
            "is_newer": False,
            "checked_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        _write_cache(stale_entry)

        fake_body = _mock_pypi_response("9.9.9")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = check_for_updates(force=True)

        assert result is not None
        latest, is_newer = result
        assert latest == "9.9.9"
        assert is_newer is True

    def test_caches_result(self) -> None:
        """Result is written to cache and in-memory."""
        fake_body = _mock_pypi_response("9.9.9")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            check_for_updates(force=True)

        # In-memory cache
        assert _updater_mod._cache is not None
        assert _updater_mod._cache["latest_version"] == "9.9.9"

        # Disk cache
        cached = _read_cache()
        assert cached is not None
        assert cached["latest_version"] == "9.9.9"

    def test_uses_disk_cache(self) -> None:
        """Does not hit network when disk cache is fresh and force=False."""
        entry = {
            "latest_version": "0.0.1",
            "current_version": __version__,
            "is_newer": False,
            "checked_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        _write_cache(entry)

        with patch("urllib.request.urlopen") as mock_urlopen:
            result = check_for_updates(force=False)
            mock_urlopen.assert_not_called()

        assert result is not None
        latest, is_newer = result
        assert latest == "0.0.1"
        assert is_newer is False


# =============================================================================
# check_in_background
# =============================================================================


class TestCheckInBackground:
    def test_spawns_daemon_thread(self) -> None:
        """Starts a daemon thread for the background check."""
        thread = check_in_background(config={"check_updates": True})
        assert thread is not None
        assert isinstance(thread, threading.Thread)
        assert thread.daemon is True
        assert thread.name == "ajo-update-check"

    def test_no_thread_when_suppressed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Does not start a thread when updates are disabled."""
        monkeypatch.setenv(NO_UPDATE_CHECK_ENV, "1")
        result = check_in_background(config={"check_updates": True})
        assert result is None  # No thread started

    def test_no_thread_when_cached(self) -> None:
        """Does not start a thread when cache is fresh."""
        entry = {
            "latest_version": "0.0.1",
            "current_version": __version__,
            "is_newer": False,
            "checked_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        _write_cache(entry)

        result = check_in_background(config={"check_updates": True})
        assert result is None  # Cache was fresh, no thread needed

    def test_already_checked_in_process(self) -> None:
        """No duplicate threads when _cache is already populated."""
        import ajo.core.updater as _updater_mod

        _updater_mod._cache = {  # noqa: SLF001
            "latest_version": "9.9.9",
            "is_newer": True,
            "current_version": __version__,
        }

        result = check_in_background(config={"check_updates": True})
        assert result is None  # Already checked


# =============================================================================
# get_cached_update
# =============================================================================


class TestGetCachedUpdate:
    def test_returns_cached_result(self) -> None:
        """Returns (version, bool) from in-memory cache."""
        import ajo.core.updater as _updater_mod

        _updater_mod._cache = {  # noqa: SLF001
            "latest_version": "9.9.9",
            "is_newer": True,
            "current_version": __version__,
        }

        result = get_cached_update()
        assert result is not None
        latest, is_newer = result
        assert latest == "9.9.9"
        assert is_newer is True

    def test_reads_from_disk(self) -> None:
        """Falls back to disk cache when in-memory is empty."""
        entry = {
            "latest_version": "9.9.9",
            "current_version": __version__,
            "is_newer": True,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_cache(entry)

        result = get_cached_update()
        assert result is not None
        latest, is_newer = result
        assert latest == "9.9.9"
        assert is_newer is True

    def test_returns_none_when_no_cache(self) -> None:
        """Returns None when no cache exists."""
        result = get_cached_update()
        assert result is None


# =============================================================================
# format_update_message
# =============================================================================


class TestFormatUpdateMessage:
    def test_contains_version_numbers(self) -> None:
        msg = format_update_message("9.9.9")
        assert __version__ in msg
        assert "9.9.9" in msg

    def test_contains_upgrade_hint(self) -> None:
        msg = format_update_message("9.9.9")
        assert "ajo upgrade" in msg


# =============================================================================
# Cache helpers
# =============================================================================


class TestCacheHelpers:
    def test_write_then_read(self) -> None:
        data = {"latest_version": "1.2.3", "current_version": "0.0.1", "is_newer": True}
        _write_cache(data)

        loaded = _read_cache()
        assert loaded is not None
        assert loaded["latest_version"] == "1.2.3"

    def test_read_missing_file(self) -> None:
        assert _read_cache() is None

    def test_read_corrupt_file(self) -> None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text("not-json", encoding="utf-8")
        assert _read_cache() is None


# =============================================================================
# _background_check (integration smoke test)
# =============================================================================


class TestBackgroundCheck:
    def test_handles_exception_gracefully(self) -> None:
        """_background_check does not raise when check_for_updates fails."""
        with patch("ajo.core.updater.check_for_updates") as mock_check:
            mock_check.side_effect = RuntimeError("unexpected")
            # Should not raise
            _background_check(config={"check_updates": True})
            mock_check.assert_called_once()
