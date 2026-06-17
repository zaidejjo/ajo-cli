"""Django Ninja API preset — modern REST API with auto OpenAPI docs.

This preset configures:
- ``django-ninja`` with a project-level NinjaAPI instance.
- Auto-generated OpenAPI 3.0 schema with Swagger UI at ``/api/docs/``.
- **Smart code generation** — scans ``models.py`` via AST and auto-generates
  Pydantic schemas, Ninja routers, and endpoint registrations.
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
class NinjaAPIPreset(AbstractPreset):
    """Django Ninja with auto-generated OpenAPI docs and Swagger UI.

    .. rubric:: Smart code generation

    After the standard scaffold, this preset will:

    1. Scan the project's ``models.py`` files using the AST-based
       :class:`~ajo.detector.ast_analyzer.ModelRelationshipAnalyzer`.
    2. Generate ``schemas.py`` (Pydantic models) and ``endpoints.py``
       (Ninja routers) in an ``api/`` directory of each app that has models.
    3. Wire the generated routers into the project-level ``api.py``.
    """

    #: Compiled regex for CamelCase → kebab-case conversion.
    _CAMEL_TO_KEBAB: re.Pattern[str] = re.compile(r"(?<!^)(?=[A-Z])")

    @classmethod
    def registry_key(cls) -> str:
        return "ninja-api"

    @property
    def name(self) -> str:
        return "Ninja API"

    @property
    def description(self) -> str:
        return "django-ninja with auto OpenAPI docs and Swagger UI"

    @property
    def dependencies(self) -> list[str]:
        return [
            "django",
            "python-dotenv",
            "django-ninja",
        ]

    @property
    def dev_dependencies(self) -> list[str]:
        return ["ruff"]

    @property
    def preview_files(self) -> list[tuple[str, int]]:
        # Includes all monolith files plus Ninja-specific additions
        return [
            ("manage.py", 2048),
            ("__init__.py", 64),
            ("settings.py", 4864),  # larger — includes Ninja config
            ("urls.py", 768),  # includes Ninja API route
            ("wsgi.py", 256),
            ("asgi.py", 256),
            ("api.py", 2048),  # project-level NinjaAPI instance
            ("templates/base.html", 2048),
        ]

    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold a Django project with Django Ninja REST API support.

        Delegates the base Django structure to :class:`MonolithPreset`,
        overlays Ninja configuration, then runs smart code generation.
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

            # No INSTALLED_APPS change needed — django-ninja works without
            # being in INSTALLED_APPS (it only needs the url config).
            # But we add optional apps if the user wants the UI.
            ninja_apps_block = (
                "    # ── Ninja API ───────────────────────────────\n"
                "    # 'ninja',  # Uncomment if using ninja management commands\n"
            )
            settings_text = settings_text.replace(
                "INSTALLED_APPS = [",
                "INSTALLED_APPS = [\n" + ninja_apps_block,
                1,
            )

            settings_path.write_text(settings_text)

            # ── 3. Create project-level api.py (NinjaAPI instance) ──────
            api_content = (
                '"""\n'
                f"Ninja API configuration for {project_name}.\n"
                "\n"
                "Auto-discovered routers from each app's ``api/endpoints.py``\n"
                "are registered here.  Generated routers are re-imported\n"
                "every time the module loads.\n"
                '"""\n'
                "from ninja import NinjaAPI\n"
                "\n"
                f"api = NinjaAPI(title='{project_name.title()} API', version='1.0.0')\n"
                "\n"
                "\n"
                "# ------------------------------------------------------------------\n"
                "# Auto-discovered app routers\n"
                "# ------------------------------------------------------------------\n"
                "# Router registration happens below.  Each app with a\n"
                "# ``api/endpoints.py`` module will be imported here.\n"
                "#\n"
                "# Example:\n"
                "#     from myapp.api.endpoints import router as myapp_router\n"
                "#     api.add_router('/myapp/', myapp_router)\n"
            )
            (pkg / "api.py").write_text(api_content)

            # ── 4. Update urls.py ────────────────────────────────────────
            urls_path = pkg / "urls.py"
            urls_content = (
                '"""\n'
                f"URL configuration for {project_name} project.\n"
                '"""\n'
                "from django.contrib import admin\n"
                "from django.urls import path\n"
                f"from {project_name}.api import api\n"
                "\n"
                "urlpatterns = [\n"
                "    path('admin/', admin.site.urls),\n"
                "    path('api/', api.urls),\n"
                "]\n"
            )
            urls_path.write_text(urls_content)

            # ── 5. Smart code generation (AST-driven) ───────────────────
            self._generate_api_artifacts(project_path, project_name)

        except OSError as exc:
            raise PresetError(f"Failed to write Ninja API preset files: {exc}") from exc

    # ══════════════════════════════════════════════════════════════════════
    # SMART CODE GENERATION (AST-driven)
    # ══════════════════════════════════════════════════════════════════════

    def _generate_api_artifacts(
        self,
        project_path: Path,
        project_name: str,
    ) -> None:
        """Scan project models and auto-generate Ninja schemas & endpoints.

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

            # Generate schemas.py (Pydantic models)
            schema_code = self._generate_schema_code(relationship)
            (api_dir / "schemas.py").write_text(
                self._wrap_generated(schema_code, "Schemas"),
                encoding="utf-8",
            )

            # Generate endpoints.py (Ninja router)
            endpoints_code = self._generate_endpoints_code(relationship, app_name)
            (api_dir / "endpoints.py").write_text(
                self._wrap_generated(
                    endpoints_code,
                    "Endpoints",
                ),
                encoding="utf-8",
            )

            generated_apps.append(app_name)

        # Wire all app routers into the project-level api.py
        if generated_apps:
            self._wire_routers(
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

    # ── Schema generation (Pydantic) ────────────────────────────────────

    def _generate_schema_code(
        self,
        relationship: Any,
    ) -> str:
        """Generate Pydantic ``ModelSchema`` code from a model relationship.

        Creates read-only fields for discovered ForeignKey / OneToOne /
        ManyToManyField relationships.
        """
        lines: list[str] = [
            "from typing import Optional",
            "from ninja import Schema, ModelSchema",
            f"from ..models import {relationship.model_name}",
            "",
            "",
            f"class {relationship.model_name}In(Schema):",
            '    """Input schema for creating/updating instances."""',
        ]

        # Add fields from relations as optional inputs
        if relationship.fields:
            for field_name, field_type in relationship.fields.items():
                lines.append(f"    {field_name}: Optional[{field_type}] = None")
        else:
            lines.append("    # TODO: Add your input fields here")
            lines.append("    pass")

        lines.append("")
        lines.append("")
        lines.append(f"class {relationship.model_name}Out(ModelSchema):")
        lines.append('    """Output schema — auto-generated from the model."""')
        lines.append("")
        lines.append("    class Meta:")
        lines.append(f"        model = {relationship.model_name}")
        lines.append("        fields = '__all__'")

        # Add relation fields as read-only output fields
        if relationship.relations:
            lines.append("")
            lines.append("    # ── Relations (auto-detected, read-only) ──")
            for rel in relationship.relations:
                rel_name = rel.get("related_name") or rel["to"].lower()
                lines.append(f"    {rel_name}: list[{rel['to']}Out] = None")

        return "\n".join(lines)

    # ── Endpoints generation (Ninja router) ─────────────────────────────

    def _generate_endpoints_code(
        self,
        relationship: Any,
        app_name: str,
    ) -> str:
        """Generate a Ninja router with CRUD endpoints for a model."""
        model_name = relationship.model_name
        route = self._CAMEL_TO_KEBAB.sub("-", model_name).lower()

        lines: list[str] = [
            "from typing import List",
            "from django.shortcuts import get_object_or_404",
            "from ninja import Router",
            f"from ..models import {model_name}",
            f"from .schemas import {model_name}In, {model_name}Out",
            "",
            "",
            f"router = Router(tags=['{model_name}'])",
            "",
            "",
            "@router.get('/', response=List[{model_name}Out])",
            f"def list_{route}(request):",
            f'    """List all {model_name} instances."""',
            f"    qs = {model_name}.objects.all()",
            "    return qs",
            "",
            "",
            "@router.get('/{id}', response={model_name}Out)",
            f"def get_{route}(request, id: int):",
            f'    """Retrieve a single {model_name} by ID."""',
            f"    return get_object_or_404({model_name}, id=id)",
            "",
            "",
            "@router.post('/', response={model_name}Out)",
            f"def create_{route}(request, payload: {model_name}In):",
            f'    """Create a new {model_name}."""',
            f"    obj = {model_name}.objects.create(**payload.dict())",
            "    return obj",
            "",
            "",
            "@router.put('/{id}', response={model_name}Out)",
            f"def update_{route}(request, id: int, payload: {model_name}In):",
            f'    """Update an existing {model_name}."""',
            f"    obj = get_object_or_404({model_name}, id=id)",
            "    for attr, value in payload.dict(exclude_unset=True).items():",
            "        setattr(obj, attr, value)",
            "    obj.save()",
            "    return obj",
            "",
            "",
            "@router.delete('/{id}', response={int})",
            f"def delete_{route}(request, id: int):",
            f'    """Delete a {model_name}."""',
            f"    obj = get_object_or_404({model_name}, id=id)",
            "    obj.delete()",
            "    return id",
        ]

        # Add relation endpoints
        if relationship.relations:
            for rel in relationship.relations:
                rel_name = rel.get("related_name") or rel["to"].lower()
                lines.append("")
                lines.append("")
                lines.append(
                    f"@router.get('/{id}/{rel_name}', response=List[{rel['to']}Out])"
                )
                lines.append(
                    f"def get_{model_name.lower()}_{rel_name}(request, id: int):"
                )
                lines.append(
                    f'    """List related {rel["to"]} for this {model_name}."""'
                )
                lines.append(f"    obj = get_object_or_404({model_name}, id=id)")
                lines.append(f"    return obj.{rel_name}.all()")

        return "\n".join(lines)

    def _wire_routers(
        self,
        project_pkg: Path,
        generated_apps: list[str],
        project_name: str,
    ) -> None:
        """Wire per-app Ninja routers into the project-level ``api.py``."""
        api_path = project_pkg / "api.py"
        if not api_path.exists():
            return

        lines: list[str] = []
        for app in sorted(set(generated_apps)):
            # Import the router from the app's api/endpoints.py
            import_stmt = f"from {app}.api.endpoints import router as {app}_router"
            register_stmt = f"api.add_router('/{app}/', {app}_router)"
            lines.append(import_stmt)
            lines.append(register_stmt)

        wiring_code = (
            "\n"
            "# ------------------------------------------------------------------\n"
            "# Auto-registered app routers (generated by AJO Ninja API Preset)\n"
            "# ------------------------------------------------------------------\n"
            + "\n".join(lines)
            + "\n"
        )

        with api_path.open("a", encoding="utf-8") as fh:
            fh.write(wiring_code)

    @staticmethod
    def _wrap_generated(code: str, title: str) -> str:
        """Wrap generated code with a header comment block."""
        sep = "#" * 60
        return (
            f"{sep}\n"
            f"# {title}\n"
            f"# Generated by AJO CLI Ninja API Preset\n"
            f"# Do not edit manually — edits will be overwritten.\n"
            f"{sep}\n\n"
            f"{code}\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    # LEGACY HELPERS
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
            "    # ── Ninja API ───────────────────────────────\n"
            "    # 'ninja',  # Uncomment if using ninja management commands\n"
            "    'django.contrib.admin',\n"
            "    'django.contrib.auth',\n"
            "    'django.contrib.contenttypes',\n"
            "    'django.contrib.sessions',\n"
            "    'django.contrib.messages',\n"
            "    'django.contrib.staticfiles',\n"
            "]\n"
            "\n"
            "MIDDLEWARE = [\n"
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
        )
