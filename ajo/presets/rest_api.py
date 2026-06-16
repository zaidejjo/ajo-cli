"""REST API Ready preset — DRF + CORS + drf-spectacular + smart code generation.

This preset configures:
- Django REST Framework with default pagination and browsable API rendering.
- ``django-cors-headers`` for CORS support.
- ``drf-spectacular`` for auto-generated OpenAPI 3.0 schema and Swagger UI.
- **Smart code generation** — scans ``models.py`` via AST and auto-generates
  serializers, viewsets, and router URL confs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ajo.core.exceptions import PresetError
from ajo.presets import register
from ajo.presets.base import AbstractPreset
from ajo.presets.monolith import MonolithPreset, _render_db_block


@register
class RestAPIPreset(AbstractPreset):
    """Django REST Framework with CORS, Swagger, and OpenAPI schema.

    .. rubric:: Smart code generation

    After the standard DRF scaffold, this preset will:

    1. Scan the project's ``models.py`` files using the AST-based
       :class:`~ajo.detector.ast_analyzer.ModelRelationshipAnalyzer`.
    2. Generate ``serializers.py``, ``views.py``, and ``urls.py``
       in an ``api/`` directory of each app that has models.
    3. Wire the generated viewsets into a project-level ``api_router.py``.
    """

    #: Compiled regex for CamelCase → kebab-case conversion.
    _CAMEL_TO_KEBAB: re.Pattern[str] = re.compile(r"(?<!^)(?=[A-Z])")

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

    @property
    def preview_files(self) -> list[tuple[str, int]]:
        # Includes all monolith files plus REST-specific additions
        return [
            ("manage.py", 2048),
            ("__init__.py", 64),
            ("settings.py", 5120),  # larger — includes DRF config
            ("urls.py", 1024),  # includes Swagger + API routes
            ("wsgi.py", 256),
            ("asgi.py", 256),
            ("api_router.py", 1024),  # project-level router
            ("templates/base.html", 2048),
        ]

    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold a Django project pre-configured for REST APIs.

        Delegates the base Django structure to :class:`MonolithPreset`,
        overlays DRF configuration, then runs smart code generation.
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

            settings_path.write_text(settings_text)

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

            # ── 4. Smart code generation (AST-driven) ──────────────────
            self._generate_api_artifacts(project_path, project_name)

        except OSError as exc:
            raise PresetError(f"Failed to write REST API preset files: {exc}") from exc

    # ══════════════════════════════════════════════════════════════════════
    # SMART CODE GENERATION (AST-driven)
    # ══════════════════════════════════════════════════════════════════════

    def _generate_api_artifacts(
        self,
        project_path: Path,
        project_name: str,
    ) -> None:
        """Scan project models and auto-generate serializers, viewsets & URLs.

        Uses :class:`~ajo.detector.ast_analyzer.ModelRelationshipAnalyzer`
        to discover models without importing or executing project code.
        """
        # Lazy import to preserve startup time and avoid circular deps
        from ajo.detector.ast_analyzer import ModelRelationshipAnalyzer

        analyzer = ModelRelationshipAnalyzer(project_path)
        models = analyzer.analyze()

        if not models:
            return  # No models — nothing to generate

        generated_apps: list[str] = []
        for model_name, relationship in models.items():
            app_name = self._resolve_app_name(project_path, model_name)
            if app_name is None:
                continue

            api_dir = project_path / app_name / "api"
            api_dir.mkdir(parents=True, exist_ok=True)

            # Generate serializers.py
            serializer_code = self._generate_serializer_code(relationship)
            (api_dir / "serializers.py").write_text(
                self._wrap_generated(serializer_code, "Serializers"),
                encoding="utf-8",
            )

            # Generate views.py
            viewset_code = self._generate_viewset_code(relationship)
            (api_dir / "views.py").write_text(
                self._wrap_generated(viewset_code, "ViewSets"),
                encoding="utf-8",
            )

            # Generate urls.py (per-app router)
            urls_code = self._generate_app_urls_code(relationship, app_name)
            (api_dir / "urls.py").write_text(
                self._wrap_generated(urls_code, "URLs"),
                encoding="utf-8",
            )

            generated_apps.append(app_name)

        # Generate a project-level router that includes all app routers
        if generated_apps:
            self._generate_project_router(
                project_path / project_name,
                generated_apps,
                project_name,
            )

    def _resolve_app_name(
        self,
        project_path: Path,
        model_name: str,
    ) -> str | None:
        """Determine which Django app directory contains *model_name*."""
        for child in project_path.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            models_file = child / "models.py"
            if not models_file.is_file():
                continue
            source = models_file.read_text(encoding="utf-8", errors="replace")
            if f"class {model_name}" in source:
                return child.name
        return None

    # ── Serializer generation ───────────────────────────────────────────

    def _generate_serializer_code(
        self,
        relationship: Any,
    ) -> str:
        """Generate DRF ``ModelSerializer`` code from a model relationship.

        Adds read-only relation fields for discovered ForeignKey,
        OneToOneField, and ManyToManyField relationships.
        """
        lines: list[str] = [
            f"class {relationship.model_name}Serializer(serializers.ModelSerializer):",
        ]

        if relationship.relations:
            lines.append("    # ── Relations (auto-detected) ──")
            for rel in relationship.relations:
                rel_name = rel.get("related_name") or rel["to"].lower()
                is_m2m = rel["type"] == "ManyToManyField"
                field_cls = "StringRelatedField" if is_m2m else "PrimaryKeyRelatedField"
                many = "True" if is_m2m else "False"
                lines.append(
                    f"    {rel_name} = serializers."
                    f"{field_cls}(many={many}, read_only=True)"
                )
            lines.append("")

        lines.extend(
            [
                "    class Meta:",
                f"        model = {relationship.model_name}",
                "        fields = '__all__'",
            ]
        )

        return "\n".join(lines)

    # ── ViewSet generation ──────────────────────────────────────────────

    def _generate_viewset_code(
        self,
        relationship: Any,
    ) -> str:
        """Generate DRF ``ModelViewSet`` code from a model relationship.

        Creates ``@action`` endpoints for every relation.
        """
        model_name = relationship.model_name
        lines: list[str] = [
            f"class {model_name}ViewSet(viewsets.ModelViewSet):",
            f'    """',
            f"    ViewSet for {model_name}.",
            "    Auto-generated from model analysis "
            f"({len(relationship.relations)} relation(s) detected).",
            f'    """',
            f"    queryset = {model_name}.objects.all()",
            f"    serializer_class = {model_name}Serializer",
            "    permission_classes = [permissions.IsAuthenticatedOrReadOnly]",
        ]

        if relationship.relations:
            lines.append("")
            for rel in relationship.relations:
                rel_name = rel.get("related_name") or rel["to"].lower()
                lines.append("    @action(detail=True, methods=['get'])")
                lines.append(f"    def {rel_name}(self, request, pk=None):")
                lines.append("        instance = self.get_object()")
                lines.append(f"        related = instance.{rel_name}.all()")
                lines.append(
                    "        serializer = self.get_serializer(related, many=True)"
                )
                lines.append("        return Response(serializer.data)")
                lines.append("")

        return "\n".join(lines)

    # ── URL generation ──────────────────────────────────────────────────

    def _generate_app_urls_code(
        self,
        relationship: Any,
        app_name: str,
    ) -> str:
        """Generate per-app ``urls.py`` with a ``DefaultRouter``."""
        route = self._CAMEL_TO_KEBAB.sub("-", relationship.model_name).lower()

        lines: list[str] = [
            "from django.urls import path, include",
            "from rest_framework.routers import DefaultRouter",
            f"from ..api.views import {relationship.model_name}ViewSet",
            "",
            "router = DefaultRouter()",
            f"router.register("
            f"r'{route}', {relationship.model_name}ViewSet, "
            f"basename='{route}'"
            f")",
            "",
            "urlpatterns = [",
            "    path('', include(router.urls)),",
            "]",
        ]

        return "\n".join(lines)

    def _generate_project_router(
        self,
        project_pkg: Path,
        generated_apps: list[str],
        project_name: str,
    ) -> None:
        """Generate ``api_router.py`` that aggregates all per-app routers."""
        router_path = project_pkg / "api_router.py"

        import_lines: list[str] = [
            "from django.urls import path, include",
        ]
        url_lines: list[str] = [
            "",
            "urlpatterns = [",
        ]

        for app in sorted(set(generated_apps)):
            import_lines.append(
                f"from {app}.api.urls import urlpatterns as {app}_urlpatterns"
            )
            url_lines.append(f"    path('{app}/', include({app}_urlpatterns)),")

        url_lines.append("]")

        router_code = "\n".join(import_lines) + "\n" + "\n".join(url_lines) + "\n"
        router_path.write_text(
            self._wrap_generated(router_code, "Project API Router"),
            encoding="utf-8",
        )

        # Wire into root urls.py
        root_urls = project_pkg / "urls.py"
        if root_urls.exists():
            content = root_urls.read_text(encoding="utf-8")
            if "api_router" not in content:
                import_stmt = (
                    f"from {project_name}.api_router import "
                    f"urlpatterns as api_urlpatterns\n"
                )
                path_entry = "    path('api/', include(api_urlpatterns)),\n"
                content = (
                    content.rstrip() + "\n" + import_stmt + "\n" + path_entry + "\n"
                )
                root_urls.write_text(content, encoding="utf-8")

    @staticmethod
    def _wrap_generated(code: str, title: str) -> str:
        """Wrap generated code with a header comment block."""
        sep = "#" * 60
        return (
            f"{sep}\n"
            f"# {title}\n"
            f"# Generated by AJO CLI REST API Preset\n"
            f"# Do not edit manually — edits will be overwritten.\n"
            f"{sep}\n\n"
            f"from rest_framework import serializers\n"
            f"from rest_framework import viewsets, permissions\n"
            f"from rest_framework.decorators import action\n"
            f"from rest_framework.response import Response\n"
            f"\n\n"
            f"{code}\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    # LEGACY HELPERS (unchanged)
    # ══════════════════════════════════════════════════════════════════════

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
