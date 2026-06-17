"""Unit tests for :class:`ajo.presets.addons.auth.AuthAddon`.

Verifies the add-on generates correct files for each preset type,
injects AUTH_USER_MODEL, creates templates, and wires URLs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons.auth import AuthAddon


@pytest.fixture
def auth_addon() -> AuthAddon:
    return AuthAddon()


@pytest.mark.asyncio
class TestAuthAddonMonolith:
    """Auth with ``preset_key = "monolith"`` — server-rendered views."""

    async def test_creates_accounts_package(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        accounts_dir = temp_project / "accounts"
        assert accounts_dir.is_dir()
        assert (accounts_dir / "__init__.py").is_file()
        assert (accounts_dir / "apps.py").is_file()

    async def test_creates_models_py(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        models_src = (temp_project / "accounts" / "models.py").read_text()
        assert "class User(AbstractUser)" in models_src
        assert "bio" in models_src

    async def test_creates_admin_py(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        admin_src = (temp_project / "accounts" / "admin.py").read_text()
        assert "UserAdmin" in admin_src

    async def test_creates_forms_py(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        forms_src = (temp_project / "accounts" / "forms.py").read_text()
        assert "CustomUserCreationForm" in forms_src

    async def test_creates_standard_views(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        views_src = (temp_project / "accounts" / "views.py").read_text()
        assert "LoginView" in views_src
        assert "SignupView" in views_src
        assert "ProfileDetailView" in views_src

    async def test_creates_monolith_urls(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        urls_src = (temp_project / "accounts" / "urls.py").read_text()
        assert "password_reset" in urls_src
        assert "profile_detail" in urls_src

    async def test_creates_templates(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        templates_dir = temp_project / "templates" / "registration"
        assert (templates_dir / "login.html").is_file()
        assert (templates_dir / "signup.html").is_file()
        assert (templates_dir / "password_reset_form.html").is_file()
        # Profile templates for monolith
        assert (templates_dir / "profile_detail.html").is_file()

    async def test_injects_auth_user_model(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert 'AUTH_USER_MODEL = "accounts.User"' in settings

    async def test_injects_jwt_settings(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "SIMPLE_JWT" in settings
        assert "CORS_ALLOWED_ORIGINS" in settings

    async def test_wires_root_urlconf(
        self, auth_addon: AuthAddon, temp_project: Path, env_config: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "config" / "urls.py").read_text()
        assert "accounts/" in urls or "accounts.urls" in urls


@pytest.mark.asyncio
class TestAuthAddonDRF:
    """Auth with ``preset_key = "rest-api"`` — DRF endpoints."""

    async def test_creates_api_endpoints(
        self, auth_addon: AuthAddon, temp_project: Path, env_config_rest: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config_rest)
        api_dir = temp_project / "accounts" / "api"
        assert (api_dir / "serializers.py").is_file()
        assert (api_dir / "views.py").is_file()
        assert (api_dir / "urls.py").is_file()
        assert (api_dir / "__init__.py").is_file()

    async def test_drf_endpoints_have_jwt(
        self, auth_addon: AuthAddon, temp_project: Path, env_config_rest: dict
    ) -> None:
        await auth_addon.apply(temp_project, "test_project", env_config_rest)
        urls = (temp_project / "accounts" / "api" / "urls.py").read_text()
        assert "TokenObtainPairView" in urls
        assert "TokenRefreshView" in urls


@pytest.mark.asyncio
class TestAuthAddonNinja:
    """Auth with ``preset_key = "ninja-api"`` — Ninja routers."""

    async def test_creates_ninja_endpoints(
        self, auth_addon: AuthAddon, temp_project: Path, env_config_ninja: dict
    ) -> None:
        # Create api.py for Ninja router injection
        api_py = temp_project / "config" / "api.py"
        api_py.write_text("from ninja import NinjaAPI\napi = NinjaAPI()\n")

        await auth_addon.apply(temp_project, "test_project", env_config_ninja)
        api_dir = temp_project / "accounts" / "api"
        assert (api_dir / "schemas.py").is_file()
        assert (api_dir / "endpoints.py").is_file()

    async def test_ninja_wires_router(
        self, auth_addon: AuthAddon, temp_project: Path, env_config_ninja: dict
    ) -> None:
        api_py = temp_project / "config" / "api.py"
        api_py.write_text("from ninja import NinjaAPI\napi = NinjaAPI()\n")

        await auth_addon.apply(temp_project, "test_project", env_config_ninja)
        api_content = api_py.read_text()
        assert "accounts_router" in api_content
        assert "add_router" in api_content


class TestAuthAddonMetadata:
    """AuthAddon class metadata."""

    def test_name_and_description(self, auth_addon: AuthAddon) -> None:
        assert auth_addon.name == "Auth & Users"
        assert auth_addon.description

    def test_dependencies(self, auth_addon: AuthAddon) -> None:
        assert "djangorestframework-simplejwt" in auth_addon.dependencies

    def test_installed_apps(self, auth_addon: AuthAddon) -> None:
        assert "accounts" in auth_addon.installed_apps
        assert "rest_framework_simplejwt" in auth_addon.installed_apps

    def test_middleware(self, auth_addon: AuthAddon) -> None:
        cors_mw = "corsheaders.middleware.CorsMiddleware"
        assert any(cors_mw in m for m in auth_addon.middleware)

    def test_settings_blocks_has_auth_user_model(self, auth_addon: AuthAddon) -> None:
        assert any("AUTH_USER_MODEL" in b for b in auth_addon.settings_blocks)

    def test_preview_files(self, auth_addon: AuthAddon) -> None:
        assert len(auth_addon.preview_files) >= 10
        assert any("accounts/admin.py" in str(f) for f in auth_addon.preview_files)
