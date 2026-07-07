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


# ═════════════════════════════════════════════════════════════════════════════
# Parallel add-on execution
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestParallelAddonExecution:
    """Verify that parallel add-on execution works correctly."""

    async def test_parallel_addons_apply_without_error(
        self, temp_project: Path, env_config: dict
    ) -> None:
        """Parallel apply of all 4 add-ons succeeds (they target diff files)."""
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        from ajo.scaffolding.engine import ScaffoldEngine

        engine = ScaffoldEngine(
            temp_project,
            env_config=env_config,
        )
        await engine._step_addon_parallel(addons)
        # No exception means success

    async def test_parallel_addons_create_same_files(
        self, temp_project: Path, env_config: dict
    ) -> None:
        """Parallel add-ons still produce all expected files."""
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        from ajo.scaffolding.engine import ScaffoldEngine

        engine = ScaffoldEngine(
            temp_project,
            env_config=env_config,
        )
        await engine._step_addon_parallel(addons)

        assert (temp_project / "accounts").is_dir()
        assert (temp_project / "core").is_dir()
        assert (temp_project / "pytest.ini").is_file()
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "AUTH_USER_MODEL" in settings

    async def test_parallel_addon_failure_collects_all_errors(
        self, temp_project: Path
    ) -> None:
        """If one add-on fails, others still run and errors are collected."""
        from unittest.mock import AsyncMock

        from ajo.presets.addons import AbstractAddon

        class FailingAddon(AbstractAddon):
            name = "fail"
            description = "Always fails"

            async def apply(
                self,
                project_path: Path,
                project_name: str,
                env_config: dict,
            ) -> None:
                raise RuntimeError("intentional failure")

        class GoodAddon(AbstractAddon):
            name = "good"
            description = "Always succeeds"

            async def apply(
                self,
                project_path: Path,
                project_name: str,
                env_config: dict,
            ) -> None:
                (project_path / "good_addon_marker").write_text("ok")

        from ajo.scaffolding.engine import ScaffoldEngine

        engine = ScaffoldEngine(
            temp_project,
            env_config={"project_name": "test_project"},
        )
        with pytest.raises(Exception, match="Add-on.*failed"):
            await engine._step_addon_parallel([FailingAddon(), GoodAddon()])

        # The good add-on should still have run
        assert (temp_project / "good_addon_marker").is_file()
