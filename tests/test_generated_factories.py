"""Verification: generated ``factories.py`` files reference correct model classes.

After applying the testing add-on, each discovered app gets a ``factories.py``
with factory classes that reference the correct model.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons import resolve_addons
from ajo.presets.addons.testing import TestingAddon


class TestGeneratedFactories:
    """Generated ``factories.py`` files reference correct models."""

    @pytest.mark.asyncio
    async def test_products_factories_has_product_factory(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        factories = (temp_project / "products" / "tests" / "factories.py").read_text()
        assert "class ProductFactory" in factories
        assert "class ReviewFactory" in factories

    @pytest.mark.asyncio
    async def test_factories_is_valid_python(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "products" / "tests" / "factories.py").read_text()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"factories.py has syntax errors: {e}")

    @pytest.mark.asyncio
    async def test_factories_import_correct_model(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "products" / "tests" / "factories.py").read_text()
        assert "from products import models" in source

    @pytest.mark.asyncio
    async def test_factories_extend_django_model_factory(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "products" / "tests" / "factories.py").read_text()
        assert "DjangoModelFactory" in source


class TestFactoryModelReferences:
    """Verify factory classes reference actual Django model classes."""

    def test_factory_meta_has_model_attribute(self) -> None:
        """Generated factory string should have a ``Meta.model =``."""
        addon = TestingAddon()
        factories = addon._generate_factories(
            "products", ["Product", "Review"], "myproject"
        )
        assert "model = models.Product" in factories
        assert "model = models.Review" in factories

    def test_factory_fallback_uses_user_model(self) -> None:
        """When no models discovered, fallback generates UserFactory."""
        addon = TestingAddon()
        factories = addon._generate_factories("accounts", [], "myproject")
        assert "class UserFactory" in factories
        assert "get_user_model()" in factories
        assert "set_password" in factories

    def test_generated_factory_is_valid_python(self) -> None:
        addon = TestingAddon()
        factories = addon._generate_factories(
            "products", ["Product", "Review"], "myproject"
        )
        try:
            ast.parse(factories)
        except SyntaxError as e:
            pytest.fail(f"Generated factory source has syntax errors: {e}")
