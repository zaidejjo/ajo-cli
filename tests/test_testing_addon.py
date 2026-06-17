"""Unit tests for :class:`ajo.presets.addons.testing.TestingAddon`.

Verifies the add-on generates pytest.ini, conftest.py, .coveragerc,
per-app test directories, factories, and test stubs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons.testing import TestingAddon


@pytest.fixture
def testing_addon() -> TestingAddon:
    return TestingAddon()


@pytest.mark.asyncio
class TestTestingAddonApply:
    """``TestingAddon.apply()``"""

    async def test_creates_pytest_ini(
        self, testing_addon: TestingAddon, temp_project: Path, env_config: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config)
        assert (temp_project / "pytest.ini").is_file()
        content = (temp_project / "pytest.ini").read_text()
        assert "DJANGO_SETTINGS_MODULE" in content

    async def test_creates_conftest_py(
        self, testing_addon: TestingAddon, temp_project: Path, env_config: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config)
        assert (temp_project / "conftest.py").is_file()
        content = (temp_project / "conftest.py").read_text()
        assert "api_client" in content
        assert "authenticated_client" in content

    async def test_creates_coveragerc(
        self, testing_addon: TestingAddon, temp_project: Path, env_config: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config)
        assert (temp_project / ".coveragerc").is_file()
        content = (temp_project / ".coveragerc").read_text()
        assert "fail_under" in content

    async def test_creates_per_app_test_dirs(
        self, testing_addon: TestingAddon, temp_project: Path, env_config: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config)
        # products app should get a tests/ dir
        products_tests = temp_project / "products" / "tests"
        assert products_tests.is_dir()
        assert (products_tests / "__init__.py").is_file()
        assert (products_tests / "factories.py").is_file()
        assert (products_tests / "test_models.py").is_file()
        assert (products_tests / "test_apis.py").is_file()

    async def test_generates_factories_for_discovered_models(
        self, testing_addon: TestingAddon, temp_project: Path, env_config: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config)
        factories = (temp_project / "products" / "tests" / "factories.py").read_text()
        assert "ProductFactory" in factories
        assert "ReviewFactory" in factories

    async def test_generates_model_tests(
        self, testing_addon: TestingAddon, temp_project: Path, env_config: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config)
        test_models = (
            temp_project / "products" / "tests" / "test_models.py"
        ).read_text()
        assert "TestProduct" in test_models
        assert "TestReview" in test_models
        assert "test_factory_create" in test_models

    async def test_generates_api_tests_for_drf(
        self, testing_addon: TestingAddon, temp_project: Path, env_config_rest: dict
    ) -> None:
        await testing_addon.apply(temp_project, "test_project", env_config_rest)
        test_apis = (temp_project / "products" / "tests" / "test_apis.py").read_text()
        assert "api_client" in test_apis or "client" in test_apis


class TestTestingAddonDiscovery:
    """``_discover_models()`` — AST-based model detection."""

    def test_discover_single_model(
        self, testing_addon: TestingAddon, temp_project: Path
    ) -> None:
        models_path = temp_project / "products" / "models.py"
        models = testing_addon._discover_models(models_path)
        assert "Product" in models
        assert "Review" in models

    def test_discover_skips_non_model_classes(
        self, testing_addon: TestingAddon, temp_project: Path
    ) -> None:
        models_path = temp_project / "products" / "models.py"
        models = testing_addon._discover_models(models_path)
        assert "NotAModel" not in models

    def test_discover_empty_file(
        self, testing_addon: TestingAddon, tmp_path: Path
    ) -> None:
        empty = tmp_path / "empty_models.py"
        empty.write_text("# No models here\n")
        models = testing_addon._discover_models(empty)
        assert models == []

    def test_discover_nonexistent_file(self, testing_addon: TestingAddon) -> None:
        models = testing_addon._discover_models(Path("/does/not/exist.py"))
        assert models == []


class TestTestingAddonFactories:
    """``_generate_factories()`` — factory code generation."""

    def test_generates_factories_for_models(self, testing_addon: TestingAddon) -> None:
        result = testing_addon._generate_factories(
            "products", ["Product", "Review"], "myproject"
        )
        assert "class ProductFactory" in result
        assert "class ReviewFactory" in result

    def test_generates_user_factory_fallback(self, testing_addon: TestingAddon) -> None:
        result = testing_addon._generate_factories("accounts", [], "myproject")
        assert "class UserFactory" in result
        assert "set_password" in result


class TestTestingAddonMetadata:
    """TestingAddon class metadata."""

    def test_name_and_description(self, testing_addon: TestingAddon) -> None:
        assert testing_addon.name == "Testing Infrastructure"
        assert testing_addon.description

    def test_dev_dependencies(self, testing_addon: TestingAddon) -> None:
        assert "pytest" in testing_addon.dev_dependencies
        assert "factory-boy" in testing_addon.dev_dependencies

    def test_preview_files(self, testing_addon: TestingAddon) -> None:
        assert any("tests/__init__.py" in str(f) for f in testing_addon.preview_files)
