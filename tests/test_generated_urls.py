"""Verification: generated ``urls.py`` and add-on URL wiring are valid.

After applying add-ons, the root ``urls.py`` and any generated app
``urls.py`` files should be syntactically valid Python.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons import resolve_addons


def _is_valid_python(source: str) -> bool:
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


@pytest.mark.asyncio
class TestGeneratedUrlsValidPython:
    """All generated urls.py files are valid Python."""

    async def test_root_urls_valid_after_auth(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "config" / "urls.py").read_text()
        assert _is_valid_python(urls)

    async def test_accounts_urls_valid(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "accounts" / "urls.py").read_text()
        assert _is_valid_python(urls)

    async def test_core_urls_valid(self, temp_project: Path, env_config: dict) -> None:
        addons = resolve_addons(["cache"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "core" / "urls.py").read_text()
        assert _is_valid_python(urls)

    async def test_all_urls_valid_after_all_addons(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        assert _is_valid_python((temp_project / "config" / "urls.py").read_text())
        assert _is_valid_python((temp_project / "accounts" / "urls.py").read_text())
        assert _is_valid_python((temp_project / "core" / "urls.py").read_text())


class TestGeneratedUrlsDjangoValid:
    """Generated urls.py can be compiled to valid Django urlpatterns.

    We can't fully ``import`` without Django being set up, but we can at
    least verify the AST form looks correct.
    """

    @staticmethod
    def _count_urlpatterns(source: str) -> int:
        """Count the number of ``path()`` calls in urlpatterns list."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return 0
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "path":
                count += 1
        return count

    @pytest.mark.asyncio
    async def test_root_has_urlpatterns(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth", "cache", "testing"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "config" / "urls.py").read_text()
        assert self._count_urlpatterns(urls) > 1

    @pytest.mark.asyncio
    async def test_accounts_has_urlpatterns(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["auth"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "accounts" / "urls.py").read_text()
        assert self._count_urlpatterns(urls) >= 4

    @pytest.mark.asyncio
    async def test_core_has_urlpatterns(
        self, temp_project: Path, env_config: dict
    ) -> None:
        addons = resolve_addons(["cache"])
        for a in addons:
            await a.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "core" / "urls.py").read_text()
        assert self._count_urlpatterns(urls) >= 1
