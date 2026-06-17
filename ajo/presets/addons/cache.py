"""Caching & Performance add-on.

Adds Redis caching, database connection pooling via django-db-connection-pool,
Django Debug Toolbar for development, and a demo cached view.
Composable on top of any preset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.presets.addons import AbstractAddon, register_addon
from ajo.presets.addons._settings import SettingsInjector


@register_addon
class CacheAddon(AbstractAddon):
    """Add Redis caching, connection pooling, and debug toolbar."""

    name = "Caching & Performance"
    description = "Redis + connection pooling + debug toolbar"
    dependencies = [
        "django-redis",
        "django-db-connection-pool",
        "django-debug-toolbar",
    ]
    compatible_presets: list[str] | None = None
    conflicts_with: list[str] = []

    installed_apps = [
        "debug_toolbar",
    ]

    middleware = [
        ("django.middleware.cache.UpdateCacheMiddleware", "first"),
        ("debug_toolbar.middleware.DebugToolbarMiddleware", "first"),
        ("django.middleware.cache.FetchFromCacheMiddleware", "last"),
    ]

    url_patterns = [
        ("__debug__/", "debug_toolbar.toolbar:debug_toolbar_urlpatterns"),
    ]

    env_vars = {
        "REDIS_URL": "redis://localhost:6379/0",
        "CACHE_TTL": "300",
        "DB_CONN_MAX_AGE": "60",
        "DB_POOL_MIN": "2",
        "DB_POOL_MAX": "10",
    }

    settings_blocks = [
        """
# ---------------------------------------------------------------------------
# Caching & Performance — Redis Cache Backend
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": os.getenv("DJANGO_SETTINGS_MODULE", "config"),
    }
}

CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
""",
        """
# ---------------------------------------------------------------------------
# Caching & Performance — Database Connection Pooling
# ---------------------------------------------------------------------------
# django-db-connection-pool replaces the standard DATABASES engine with
# a pooled version.  The pool settings below are safe for development;
# tune CONN_MAX_AGE / pool sizes for production.
DATABASES["default"]["ENGINE"] = "django_db_connection_pool.backends.postgresql"  # type: ignore[index]
DATABASES["default"]["CONN_MAX_AGE"] = int(os.getenv("DB_CONN_MAX_AGE", "60"))
DATABASES["default"]["POOL_OPTIONS"] = {
    "POOL_SIZE": int(os.getenv("DB_POOL_MIN", "2")),
    "MAX_OVERFLOW": int(os.getenv("DB_POOL_MAX", "10")),
}
""",
        """
# ---------------------------------------------------------------------------
# Caching & Performance — Django Debug Toolbar
# ---------------------------------------------------------------------------
import sys

INTERNAL_IPS = [
    "127.0.0.1",
]

# Only enable the toolbar in non-test development environments.
if "test" not in sys.argv and "pytest" not in sys.modules:
    INSTALLED_APPS += ["debug_toolbar"]  # type: ignore[list-item]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # type: ignore[operator]
""",
    ]

    preview_files: list[tuple[str, int]] = [
        ("core/views.py", 512),
        ("core/urls.py", 256),
    ]

    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Inject caching settings and generate demo cached view."""
        await self._inject_settings(project_path)
        await self._wire_urls(project_path, project_name)
        await self._update_env(project_path)
        await self._generate_demo_view(project_path, project_name)

    async def _generate_demo_view(
        self,
        project_path: Path,
        project_name: str,
    ) -> None:
        """Generate a ``core/`` app with a demo cached endpoint."""
        core_dir = project_path / "core"
        core_dir.mkdir(parents=True, exist_ok=True)

        self._write_file(core_dir / "__init__.py", "")

        self._write_file(
            core_dir / "views.py",
            '''"""Demo views demonstrating Redis caching with django-redis."""

import time

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie


@vary_on_cookie
@cache_page(settings.CACHE_TTL)
def cached_demo_view(request):
    """Return a JSON response with the current server timestamp.

    This view is cached for ``CACHE_TTL`` seconds (default 300).
    Refresh the page to verify the timestamp only changes once
    the cache expires.
    """
    return JsonResponse({
        "message": "This response is cached with Redis.",
        "cached_at": time.time(),
        "cache_ttl_seconds": settings.CACHE_TTL,
    })
''',
        )

        self._write_file(
            core_dir / "urls.py",
            """from django.urls import path

from . import views

urlpatterns = [
    path("cache-demo/", views.cached_demo_view, name="cache_demo"),
]
""",
        )

        # Wire core/urls.py into root urlconf
        project_pkg = (
            project_path / project_name
            if (project_path / project_name).exists()
            else project_path / "config"
        )
        urls_path = project_pkg / "urls.py"
        if urls_path.exists():
            text = urls_path.read_text(encoding="utf-8")
            text = SettingsInjector.inject_urls(text, [("", "core.urls")])
            urls_path.write_text(text)
