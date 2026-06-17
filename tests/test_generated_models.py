"""Verification: generated ``models.py`` files contain valid Django model classes.

After applying add-ons (especially auth), the generated ``models.py`` should
contain properly structured Django model classes that would compile correctly.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons import resolve_addons


@pytest.mark.asyncio
class TestGeneratedAccountModels:
    """``accounts/models.py`` contains valid Django model definitions."""

    async def test_accounts_models_exist(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        assert (temp_project / "accounts" / "models.py").is_file()

    async def test_accounts_models_is_valid_python(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "accounts" / "models.py").read_text()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"accounts/models.py has syntax errors: {e}")

    async def test_accounts_models_has_user_class(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "accounts" / "models.py").read_text()
        assert "class User(AbstractUser)" in source

    async def test_accounts_models_has_profile_fields(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "accounts" / "models.py").read_text()
        assert "bio" in source
        assert "avatar" in source

    async def test_accounts_models_has_str_method(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "accounts" / "models.py").read_text()
        assert "def __str__" in source


class TestGeneratedModelClasses:
    """Verifies generated models use correct Django base classes."""

    @staticmethod
    def _extract_model_classes(source: str) -> list[str]:
        """Return names of classes that inherit from Django model bases."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        django_bases = {"Model", "AbstractUser", "AbstractBaseUser"}
        models = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                base_name = (
                    base.attr
                    if isinstance(base, ast.Attribute)
                    else base.id
                    if isinstance(base, ast.Name)
                    else ""
                )
                if base_name in django_bases:
                    models.append(node.name)
                    break
        return models

    @pytest.mark.asyncio
    async def test_accounts_user_inherits_abstract_user(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        source = (temp_project / "accounts" / "models.py").read_text()
        model_classes = self._extract_model_classes(source)
        assert "User" in model_classes

    def test_discovered_models_are_correct(self, sample_models: str) -> None:
        """Verify _extract_model_classes picks up Product and Review."""
        models = self._extract_model_classes(sample_models)
        assert "Product" in models
        assert "Review" in models
        assert "NotAModel" not in models
