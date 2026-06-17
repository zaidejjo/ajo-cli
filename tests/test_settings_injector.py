"""Unit tests for :class:`ajo.presets.addons._settings.SettingsInjector`.

Verifies that apps, middleware, env vars, URLs, and code blocks are
injected correctly into sample settings.py / urls.py / .env content.
"""

from __future__ import annotations

import pytest

from ajo.presets.addons._settings import SettingsInjector


class TestInjectApps:
    """``SettingsInjector.inject_apps()``"""

    def test_inject_single_app(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_apps(sample_settings, ["myapp"])
        assert result != sample_settings
        assert "'myapp'," in result
        # Original apps should still be present
        assert "'django.contrib.admin'," in result

    def test_inject_multiple_apps(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_apps(sample_settings, ["myapp", "corsheaders"])
        assert "'myapp'," in result
        assert "'corsheaders'," in result

    def test_skip_duplicates(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_apps(sample_settings, ["django.contrib.admin"])
        # Should be unchanged since admin is already present
        assert result == sample_settings

    def test_inject_no_matches_falls_back(self) -> None:
        text = "NO_INSTALLED_APPS_HERE"
        result = SettingsInjector.inject_apps(text, ["myapp"])
        assert result == text  # unchanged

    def test_inject_adds_header_comment(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_apps(sample_settings, ["myapp"])
        assert "# ── Add-ons ──" in result


class TestInjectMiddleware:
    """``SettingsInjector.inject_middleware()``"""

    def test_inject_first(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_middleware(
            sample_settings,
            [("corsheaders.middleware.CorsMiddleware", "first")],
        )
        idx = result.index("'corsheaders.middleware.CorsMiddleware',")
        security_idx = result.index("'django.middleware.security.SecurityMiddleware',")
        assert idx < security_idx, (
            "First middleware should appear before SecurityMiddleware"
        )

    def test_inject_last(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_middleware(
            sample_settings,
            [("my.middleware.LastMiddleware", "last")],
        )
        # Last middleware should appear before the closing ]
        assert "'my.middleware.LastMiddleware'," in result
        xframe_idx = result.index(
            "'django.middleware.clickjacking.XFrameOptionsMiddleware',"
        )
        last_idx = result.index("'my.middleware.LastMiddleware',")
        assert xframe_idx < last_idx, (
            "Last middleware should come after existing entries"
        )

    def test_inject_first_and_last(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_middleware(
            sample_settings,
            [
                ("first.middleware.FirstMiddleware", "first"),
                ("last.middleware.LastMiddleware", "last"),
            ],
        )
        first_idx = result.index("'first.middleware.FirstMiddleware',")
        last_idx = result.index("'last.middleware.LastMiddleware',")
        security_idx = result.index("'django.middleware.security.SecurityMiddleware',")
        xframe_idx = result.index(
            "'django.middleware.clickjacking.XFrameOptionsMiddleware',"
        )
        assert first_idx < security_idx
        assert xframe_idx < last_idx

    def test_skip_duplicate_middleware(self, sample_settings: str) -> None:
        # Inject something already in MIDDLEWARE
        result = SettingsInjector.inject_middleware(
            sample_settings,
            [("django.middleware.security.SecurityMiddleware", "first")],
        )
        # Count occurrences — should be exactly 1
        count = result.count("'django.middleware.security.SecurityMiddleware',")
        assert count == 1, f"Expected 1 occurrence, found {count}"


class TestAppendBlock:
    """``SettingsInjector.append_block()``"""

    def test_append_simple_block(self, sample_settings: str) -> None:
        block = "# MY CUSTOM BLOCK\nMY_VAR = 42\n"
        result = SettingsInjector.append_block(sample_settings, block)
        assert result.endswith(block + "\n") or block in result
        assert "# MY CUSTOM BLOCK" in result

    def test_append_adds_blank_line_separator(self) -> None:
        text = "EXISTING_CODE"
        result = SettingsInjector.append_block(text, "NEW_BLOCK")
        assert result == "EXISTING_CODE\n\nNEW_BLOCK\n"


class TestInjectEnv:
    """``SettingsInjector.inject_env()``"""

    def test_inject_new_var(self, sample_env: str) -> None:
        result = SettingsInjector.inject_env(sample_env, {"MY_KEY": "my_value"})
        assert "MY_KEY=my_value" in result

    def test_skip_existing_var(self, sample_env: str) -> None:
        result = SettingsInjector.inject_env(sample_env, {"SECRET_KEY": "override"})
        assert "SECRET_KEY=dummy" in result  # original preserved
        assert "SECRET_KEY=override" not in result  # not overridden

    def test_inject_multiple_vars(self, sample_env: str) -> None:
        result = SettingsInjector.inject_env(sample_env, {"VAR_A": "a", "VAR_B": "b"})
        assert "VAR_A=a" in result
        assert "VAR_B=b" in result

    def test_empty_env(self) -> None:
        result = SettingsInjector.inject_env("", {"KEY": "val"})
        assert "KEY=val" in result


class TestInjectUrls:
    """``SettingsInjector.inject_urls()``"""

    def test_inject_into_existing_urlpatterns(self, sample_urls: str) -> None:
        result = SettingsInjector.inject_urls(sample_urls, [("auth/", "accounts.urls")])
        assert (
            "path('auth/', include('accounts.urls'))," in result
            or "path('auth/', accounts_urlpatterns)," in result
        )

    def test_inject_multiple_patterns(self, sample_urls: str) -> None:
        result = SettingsInjector.inject_urls(
            sample_urls,
            [
                ("auth/", "accounts.urls"),
                ("api/", "api.urls"),
            ],
        )
        # Both patterns should appear in urlpatterns
        assert "auth/" in result
        assert "api/" in result

    def test_create_urlpatterns_if_missing(self) -> None:
        text = "# Just a comment\n"
        result = SettingsInjector.inject_urls(text, [("test/", "test.urls")])
        assert "urlpatterns = [" in result


class TestEdgeCases:
    """Edge cases for SettingsInjector."""

    def test_empty_apps_list(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_apps(sample_settings, [])
        assert result == sample_settings

    def test_empty_middleware_list(self, sample_settings: str) -> None:
        result = SettingsInjector.inject_middleware(sample_settings, [])
        assert result == sample_settings

    def test_empty_env_vars(self, sample_env: str) -> None:
        result = SettingsInjector.inject_env(sample_env, {})
        assert result == sample_env

    def test_empty_url_patterns(self, sample_urls: str) -> None:
        result = SettingsInjector.inject_urls(sample_urls, [])
        assert result == sample_urls

    def test_unusual_installed_apps_formatting(self) -> None:
        """Non-standard whitespace should still be handled."""
        text = "INSTALLED_APPS = ['app1',]"
        result = SettingsInjector.inject_apps(text, ["myapp"])
        assert "'myapp'," in result
