"""Unit tests for :class:`ajo.presets.addons.security.SecurityAddon`.

Verifies the add-on injects django-axes config, CSP policies,
HTTPS/secure settings, and security middleware.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons.security import SecurityAddon


@pytest.fixture
def security_addon() -> SecurityAddon:
    return SecurityAddon()


@pytest.mark.asyncio
class TestSecurityAddonApply:
    """``SecurityAddon.apply()``"""

    async def test_injects_axes_config(
        self, security_addon: SecurityAddon, temp_project: Path, env_config: dict
    ) -> None:
        await security_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "AXES_ENABLED" in settings
        assert "AXES_FAILURE_LIMIT" in settings

    async def test_injects_axes_authentication_backends(
        self, security_addon: SecurityAddon, temp_project: Path, env_config: dict
    ) -> None:
        await security_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "axes.backends.AxesBackend" in settings

    async def test_injects_csp_settings(
        self, security_addon: SecurityAddon, temp_project: Path, env_config: dict
    ) -> None:
        await security_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "CSP_DEFAULT_SRC" in settings
        assert "CSP_STYLE_SRC" in settings

    async def test_injects_secure_settings(
        self, security_addon: SecurityAddon, temp_project: Path, env_config: dict
    ) -> None:
        await security_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "SECURE_HSTS_SECONDS" in settings
        assert "SECURE_CONTENT_TYPE_NOSNIFF" in settings
        assert "SESSION_COOKIE_HTTPONLY" in settings
        assert "CSRF_COOKIE_SECURE" in settings
        assert "X_FRAME_OPTIONS" in settings

    async def test_injects_axes_installed_app(
        self, security_addon: SecurityAddon, temp_project: Path, env_config: dict
    ) -> None:
        await security_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "axes" in settings or "'axes'" in settings

    async def test_updates_env(
        self, security_addon: SecurityAddon, temp_project: Path, env_config: dict
    ) -> None:
        await security_addon.apply(temp_project, "test_project", env_config)
        env_text = (temp_project / ".env").read_text()
        assert "AXES_ENABLED" in env_text
        assert "AXES_FAILURE_LIMIT" in env_text
        assert "CSP_DEFAULT_SRC" in env_text


class TestSecurityAddonMetadata:
    """SecurityAddon class metadata."""

    def test_name_and_description(self, security_addon: SecurityAddon) -> None:
        assert security_addon.name == "Security Hardening"
        assert security_addon.description

    def test_dependencies(self, security_addon: SecurityAddon) -> None:
        assert "django-axes" in security_addon.dependencies
        assert "django-otp" in security_addon.dependencies
        assert "django-csp" in security_addon.dependencies

    def test_installed_apps(self, security_addon: SecurityAddon) -> None:
        assert "axes" in security_addon.installed_apps
        assert "django_otp" in security_addon.installed_apps
        assert "csp" in security_addon.installed_apps

    def test_middleware(self, security_addon: SecurityAddon) -> None:
        mw = security_addon.middleware
        paths = [p for p, _ in mw]
        assert any("AxesMiddleware" in p for p in paths)
        assert any("OTPMiddleware" in p for p in paths)
        assert any("CSPMiddleware" in p for p in paths)

    def test_settings_blocks(self, security_addon: SecurityAddon) -> None:
        all_blocks = " ".join(security_addon.settings_blocks)
        assert "AXES_" in all_blocks
        assert "CSP_" in all_blocks
        assert "SECURE_" in all_blocks
