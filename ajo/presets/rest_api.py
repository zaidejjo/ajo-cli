"""REST API Ready preset — Django REST Framework + drf-spectacular.

This preset configures:
- Django REST Framework with default pagination and browsable API rendering.
- ``django-cors-headers`` for CORS support.
- ``drf-spectacular`` for auto-generated OpenAPI 3.0 schema and Swagger UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.core.exceptions import PresetError
from ajo.presets import register
from ajo.presets.base import AbstractPreset
from ajo.presets.monolith import MonolithPreset, _render_db_block


@register
class RestAPIPreset(AbstractPreset):
    """Django REST Framework with CORS, Swagger, and OpenAPI schema."""

    @classmethod
    def registry_key(cls) -> str:
        return "rest-api"

    @property
    def name(self) -> str:
        return "REST API Ready"

    @property
    def description(self) -> str:
        return "DRF + CORS + drf-spectacular with auto OpenAPI docs"

    @property
    def dependencies(self) -> list[str]:
        return [
            "django",
            "python-dotenv",
            "djangorestframework",
            "django-cors-headers",
            "drf-spectacular",
        ]

    @property
    def dev_dependencies(self) -> list[str]:
        return ["ruff"]

    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold a Django project pre-configured for REST APIs.

        Delegates the base Django structure to :class:`MonolithPreset`,
        then overlays the DRF configuration on top.
        """
        project_name: str = env_config["project_name"]
        db_type: str = env_config.get("db_type", "sqlite")
        db_config: dict[str, Any] = env_config.get("db_config", {})

        try:
            # ── 1. Base Django structure (via MonolithPreset) ───────────
            monolith = MonolithPreset()
            await monolith.scaffold(project_path, env_config)

            pkg = project_path / project_name

            # ── 2. Update settings.py ───────────────────────────────────
            settings_path = pkg / "settings.py"
            if settings_path.exists():
                settings_text = settings_path.read_text(encoding="utf-8")
            else:
                settings_text = self._default_settings(project_name, db_type, db_config)
                pkg.mkdir(exist_ok=True)

            # Inject INSTALLED_APPS additions
            rest_apps_block = (
                "    # ── REST Framework ─────────────────────────────\n"
                "    'rest_framework',\n"
                "    'corsheaders',\n"
                "    'drf_spectacular',\n"
            )
            settings_text = settings_text.replace(
                "INSTALLED_APPS = [",
                "INSTALLED_APPS = [\n" + rest_apps_block,
                1,
            )
            # Replace the first occurrence only

            # Inject MIDDLEWARE additions (corsheaders must be first)
            cors_mw_block = (
                "    # ── CORS ────────────────────────────────────────\n"
                "    'corsheaders.middleware.CorsMiddleware',\n"
                "    'django.middleware.common.CommonMiddleware',\n"
            )
            settings_text = settings_text.replace(
                "'django.middleware.common.CommonMiddleware',",
                cors_mw_block,
                1,
            )

            # Inject REST_FRAMEWORK and SPECTACULAR_SETTINGS at the end
            rest_config_block = (
                "\n"
                "# ============================================================\n"
                "# REST FRAMEWORK CONFIGURATION\n"
                "# ============================================================\n"
                "REST_FRAMEWORK = {\n"
                "    'DEFAULT_PAGINATION_CLASS':\n"
                "        'rest_framework.pagination.PageNumberPagination',\n"
                "    'PAGE_SIZE': 25,\n"
                "    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',\n"
                "    'DEFAULT_RENDERER_CLASSES': [\n"
                "        'rest_framework.renderers.JSONRenderer',\n"
                "        'rest_framework.renderers.BrowsableAPIRenderer',\n"
                "    ],\n"
                "}\n"
                "\n"
                "# ============================================================\n"
                "# OPENAPI / SWAGGER CONFIGURATION (drf-spectacular)\n"
                "# ============================================================\n"
                "SPECTACULAR_SETTINGS = {\n"
                f"    'TITLE': '{project_name.title()} API',\n"
                "    'DESCRIPTION': 'Auto-generated API documentation',\n"
                "    'VERSION': '1.0.0',\n"
                "    'SERVE_INCLUDE_SCHEMA': False,\n"
                "}\n"
            )
            settings_text += rest_config_block

            (settings_path).write_text(settings_text)

            # ── 3. Update urls.py with Swagger UI and API root ──────────
            urls_path = pkg / "urls.py"
            urls_content = (
                '"""\n'
                f"URL configuration for {project_name} project.\n"
                '"""\n'
                "from django.contrib import admin\n"
                "from django.urls import path, include\n"
                "from drf_spectacular.views import (\n"
                "    SpectacularAPIView,\n"
                "    SpectacularSwaggerView,\n"
                "    SpectacularRedocView,\n"
                ")\n"
                "\n"
                "urlpatterns = [\n"
                "    path('admin/', admin.site.urls),\n"
                "    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),\n"
                "    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'),\n"
                "         name='swagger-ui'),\n"
                "    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'),\n"
                "         name='redoc'),\n"
                "]\n"
            )
            urls_path.write_text(urls_content)

        except OSError as exc:
            raise PresetError(f"Failed to write REST API preset files: {exc}") from exc

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _default_settings(
        project_name: str,
        db_type: str,
        db_config: dict[str, Any],
    ) -> str:
        """Generate a minimal settings.py if the monolith step somehow
        did not produce one."""
        db_block = _render_db_block(db_type, db_config)

        return (
            '"""\n'
            f"Django settings for {project_name} project.\n"
            '"""\n'
            "import os\n"
            "from pathlib import Path\n"
            "from dotenv import load_dotenv\n"
            "\n"
            "load_dotenv()\n"
            "\n"
            "BASE_DIR = Path(__file__).resolve().parent.parent\n"
            "\n"
            "SECRET_KEY = os.getenv('SECRET_KEY')\n"
            "DEBUG = os.getenv('DEBUG', 'True') == 'True'\n"
            "ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')\n"
            "\n"
            "INSTALLED_APPS = [\n"
            "    'django.contrib.admin',\n"
            "    'django.contrib.auth',\n"
            "    'django.contrib.contenttypes',\n"
            "    'django.contrib.sessions',\n"
            "    'django.contrib.messages',\n"
            "    'django.contrib.staticfiles',\n"
            "\n"
            "    # ── REST Framework ─────────────────────────────\n"
            "    'rest_framework',\n"
            "    'corsheaders',\n"
            "    'drf_spectacular',\n"
            "]\n"
            "\n"
            "MIDDLEWARE = [\n"
            "    # ── CORS ────────────────────────────────────────\n"
            "    'corsheaders.middleware.CorsMiddleware',\n"
            "    'django.middleware.security.SecurityMiddleware',\n"
            "    'django.contrib.sessions.middleware.SessionMiddleware',\n"
            "    'django.middleware.common.CommonMiddleware',\n"
            "    'django.middleware.csrf.CsrfViewMiddleware',\n"
            "    'django.contrib.auth.middleware.AuthenticationMiddleware',\n"
            "    'django.contrib.messages.middleware.MessageMiddleware',\n"
            "    'django.middleware.clickjacking.XFrameOptionsMiddleware',\n"
            "]\n"
            "\n"
            f"ROOT_URLCONF = '{project_name}.urls'\n"
            "\n"
            "TEMPLATES = [\n"
            "    {\n"
            "        'BACKEND': 'django.template.backends.django.DjangoTemplates',\n"
            "        'DIRS': [BASE_DIR / 'templates'],\n"
            "        'APP_DIRS': True,\n"
            "        'OPTIONS': {\n"
            "            'context_processors': [\n"
            "                'django.template.context_processors.debug',\n"
            "                'django.template.context_processors.request',\n"
            "                'django.contrib.auth.context_processors.auth',\n"
            "                'django.contrib.messages.context_processors.messages',\n"
            "            ],\n"
            "        },\n"
            "    },\n"
            "]\n"
            "\n"
            f"WSGI_APPLICATION = '{project_name}.wsgi.application'\n"
            "\n"
            f"{db_block}\n"
            "\n"
            "AUTH_PASSWORD_VALIDATORS = [\n"
            "    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},\n"
            "    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},\n"
            "    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},\n"
            "    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},\n"
            "]\n"
            "\n"
            "LANGUAGE_CODE = 'en-us'\n"
            "TIME_ZONE = 'UTC'\n"
            "USE_I18N = True\n"
            "USE_TZ = True\n"
            "\n"
            "STATIC_URL = 'static/'\n"
            "DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'\n"
            "\n"
            "# ============================================================\n"
            "# REST FRAMEWORK CONFIGURATION\n"
            "# ============================================================\n"
            "REST_FRAMEWORK = {\n"
            "    'DEFAULT_PAGINATION_CLASS':\n"
            "        'rest_framework.pagination.PageNumberPagination',\n"
            "    'PAGE_SIZE': 25,\n"
            "    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',\n"
            "    'DEFAULT_RENDERER_CLASSES': [\n"
            "        'rest_framework.renderers.JSONRenderer',\n"
            "        'rest_framework.renderers.BrowsableAPIRenderer',\n"
            "    ],\n"
            "}\n"
            "\n"
            "# ============================================================\n"
            "# OPENAPI / SWAGGER CONFIGURATION (drf-spectacular)\n"
            "# ============================================================\n"
            "SPECTACULAR_SETTINGS = {\n"
            f"    'TITLE': '{project_name.title()} API',\n"
            "    'DESCRIPTION': 'Auto-generated API documentation',\n"
            "    'VERSION': '1.0.0',\n"
            "    'SERVE_INCLUDE_SCHEMA': False,\n"
            "}\n"
        )
