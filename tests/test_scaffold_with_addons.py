"""Integration test: full scaffold pipeline with all 4 add-ons.

Verifies that applying all add-ons to a scaffolded project directory
produces all expected files.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons import resolve_addons


@pytest.mark.asyncio
class TestScaffoldWithAllAddons:
    """Apply all 4 add-ons and verify the complete file tree."""

    async def test_all_addons_apply_without_error(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        # No exception means success

    async def test_all_addons_create_accounts_app(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        assert (temp_project / "accounts").is_dir()
        assert (temp_project / "accounts" / "models.py").is_file()
        assert (temp_project / "accounts" / "admin.py").is_file()

    async def test_all_addons_create_core_app(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        assert (temp_project / "core").is_dir()
        assert (temp_project / "core" / "views.py").is_file()

    async def test_all_addons_create_test_config(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        assert (temp_project / "pytest.ini").is_file()
        assert (temp_project / ".coveragerc").is_file()
        assert (temp_project / "conftest.py").is_file()

    async def test_all_addons_create_per_app_test_dirs(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        # products app should have tests/ from testing addon
        assert (temp_project / "products" / "tests").is_dir()
        assert (temp_project / "products" / "tests" / "factories.py").is_file()

    async def test_all_addons_inject_settings(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        # Auth
        assert "AUTH_USER_MODEL" in settings
        # Cache
        assert "CACHES" in settings
        # Security
        assert "AXES_ENABLED" in settings
        assert "CSP_DEFAULT_SRC" in settings

    async def test_all_addons_update_env(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        env = (temp_project / ".env").read_text()
        # Auth
        assert "ACCESS_TOKEN_LIFETIME" in env
        # Cache
        assert "REDIS_URL" in env
        # Security
        assert "AXES_ENABLED" in env

    async def test_all_addons_generate_templates(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for addon in addons:
            await addon.apply(temp_project, "test_project", env_config)
        templates = temp_project / "templates" / "registration"
        assert (templates / "login.html").is_file()
        assert (templates / "signup.html").is_file()

    async def test_addon_applies_idempotent(
        self, temp_project: Path, env_config: dict
    ) -> None:
        """Running apply() twice should not raise or corrupt files."""
        addons = resolve_addons(["auth", "cache"])
        for _ in range(2):
            for addon in addons:
                await addon.apply(temp_project, "test_project", env_config)
        # Settings should still be valid Python
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "AUTH_USER_MODEL" in settings
        assert "CACHES" in settings
