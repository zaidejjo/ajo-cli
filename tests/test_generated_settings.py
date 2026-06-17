"""Verification: generated ``settings.py`` is valid Python.

After applying add-ons, the ``settings.py`` file should be syntactically
valid Python and contain critical configuration keys.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons import resolve_addons


def _is_valid_python(source: str) -> bool:
    """Return True if *source* is syntactically valid Python."""
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


@pytest.mark.asyncio
class TestGeneratedSettingsValidPython:
    """Generated settings.py is valid Python after add-on injection."""

    async def test_settings_is_valid_python_after_auth(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert _is_valid_python(settings), "settings.py has syntax errors"

    async def test_settings_is_valid_python_after_cache(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["cache"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert _is_valid_python(settings), "settings.py has syntax errors"

    async def test_settings_is_valid_python_after_security(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["security"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert _is_valid_python(settings), "settings.py has syntax errors"

    async def test_settings_is_valid_python_after_all(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert _is_valid_python(settings), "settings.py has syntax errors"


class TestGeneratedSettingsContainsKeys:
    """Generated settings.py contains required configuration keys."""

    @pytest.mark.asyncio
    async def test_has_auth_keys(self, temp_project: Path, env_config: dict) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "AUTH_USER_MODEL" in settings
        assert "SIMPLE_JWT" in settings
        assert "CORS_ALLOWED_ORIGINS" in settings

    @pytest.mark.asyncio
    async def test_has_cache_keys(self, temp_project: Path, env_config: dict) -> None:
        addons = resolve_addons(["cache"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "CACHES" in settings
        assert "CACHE_TTL" in settings
        assert "django_redis" in settings

    @pytest.mark.asyncio
    async def test_has_security_keys(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["security"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "AXES_ENABLED" in settings
        assert "CSP_DEFAULT_SRC" in settings
        assert "SECURE_HSTS_SECONDS" in settings
        assert "X_FRAME_OPTIONS" in settings
