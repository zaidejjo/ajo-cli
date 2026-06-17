"""Unit tests for :class:`ajo.presets.addons.cache.CacheAddon`.

Verifies the add-on injects the CACHES block, correct middleware
ordering, creates demo view, and wires core URLs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ajo.presets.addons.cache import CacheAddon


@pytest.fixture
def cache_addon() -> CacheAddon:
    return CacheAddon()


@pytest.mark.asyncio
class TestCacheAddonApply:
    """``CacheAddon.apply()``"""

    async def test_injects_caches_block(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "CACHES" in settings
        assert "django_redis.cache.RedisCache" in settings

    async def test_injects_cache_ttl(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "CACHE_TTL" in settings

    async def test_injects_pooling_config(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "POOL_OPTIONS" in settings
        assert "django_db_connection_pool" in settings

    async def test_injects_debug_toolbar(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        settings = (temp_project / "config" / "settings.py").read_text()
        assert "debug_toolbar" in settings or "INTERNAL_IPS" in settings

    async def test_creates_demo_view(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        views_src = (temp_project / "core" / "views.py").read_text()
        assert "cache_page" in views_src
        assert "cached_demo_view" in views_src

    async def test_creates_core_urls(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        urls_src = (temp_project / "core" / "urls.py").read_text()
        assert "cache_demo" in urls_src

    async def test_wires_debug_toolbar_urls(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        urls = (temp_project / "config" / "urls.py").read_text()
        assert "__debug__" in urls

    async def test_updates_env(
        self, cache_addon: CacheAddon, temp_project: Path, env_config: dict
    ) -> None:
        await cache_addon.apply(temp_project, "test_project", env_config)
        env_text = (temp_project / ".env").read_text()
        assert "REDIS_URL" in env_text
        assert "CACHE_TTL" in env_text


class TestCacheAddonMetadata:
    """CacheAddon class metadata."""

    def test_name_and_description(self, cache_addon: CacheAddon) -> None:
        assert cache_addon.name == "Caching & Performance"
        assert cache_addon.description

    def test_dependencies(self, cache_addon: CacheAddon) -> None:
        assert "django-redis" in cache_addon.dependencies
        assert "django-debug-toolbar" in cache_addon.dependencies

    def test_middleware_ordering(self, cache_addon: CacheAddon) -> None:
        """UpdateCacheMiddleware must be first, FetchFromCacheMiddleware last."""
        mw = cache_addon.middleware
        first_items = [p for p, pos in mw if pos == "first"]
        last_items = [p for p, pos in mw if pos == "last"]
        assert any("UpdateCacheMiddleware" in p for p in first_items)
        assert any("FetchFromCacheMiddleware" in p for p in last_items)

    def test_preview_files(self, cache_addon: CacheAddon) -> None:
        assert len(cache_addon.preview_files) >= 2
        assert any("core/views.py" in str(f) for f in cache_addon.preview_files)
