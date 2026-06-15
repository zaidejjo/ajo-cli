"""GraphQL API preset — Graphene-Django with Relay support.

This preset configures:
- ``graphene-django`` with a pre-scaffolded ``schema.py``.
- Relay node structure for pagination and object identification.
- GraphiQL IDE enabled for development.
- A sample query type for rapid prototyping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.core.exceptions import PresetError
from ajo.presets import register
from ajo.presets.base import AbstractPreset
from ajo.presets.monolith import MonolithPreset, _render_db_block


@register
class GraphQLPreset(AbstractPreset):
    """Graphene-Django with Relay schema and GraphiQL IDE."""

    @classmethod
    def registry_key(cls) -> str:
        return "graphql-api"

    @property
    def name(self) -> str:
        return "GraphQL API"

    @property
    def description(self) -> str:
        return "Graphene + Relay schema with GraphiQL IDE"

    @property
    def dependencies(self) -> list[str]:
        return ["django", "python-dotenv", "graphene-django"]

    @property
    def dev_dependencies(self) -> list[str]:
        return ["ruff"]

    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold a Django project with GraphQL support.

        Delegates the base Django structure to :class:`MonolithPreset`,
        then overlays the Graphene schema, settings, and URL routing.
        """
        project_name: str = env_config["project_name"]
        db_type: str = env_config.get("db_type", "sqlite")
        db_config: dict[str, Any] = env_config.get("db_config", {})

        try:
            # ── 1. Base Django structure ────────────────────────────────
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
                (settings_path).write_text("")

            # Inject graphene into INSTALLED_APPS
            graphql_app_block = (
                "    # ── GraphQL ────────────────────────────────\n"
                "    'graphene_django',\n"
            )
            settings_text = settings_text.replace(
                "INSTALLED_APPS = [",
                "INSTALLED_APPS = [\n" + graphql_app_block,
                1,
            )

            # Append GRAPHENE settings
            graphql_settings = (
                "\n"
                "# ============================================================\n"
                "# GRAPHQL CONFIGURATION\n"
                "# ============================================================\n"
                "GRAPHENE = {\n"
                f"    'SCHEMA': '{project_name}.schema.schema',\n"
                "    'MIDDLEWARE': [\n"
                "        'graphene_django.debug.DjangoDebugMiddleware',\n"
                "    ],\n"
                "}\n"
            )
            settings_text += graphql_settings
            settings_path.write_text(settings_text)

            # ── 3. Create schema.py with Relay structure ─────────────────
            schema_content = (
                '"""\n'
                f"GraphQL schema for {project_name}.\n"
                "\n"
                "Provides a Relay-compatible schema with:\n"
                "- A :class:`Query` root type for data fetching.\n"
                "- Sample node for rapid prototyping.\n"
                "- Django debug middleware enabled in development.\n"
                '"""\n'
                "import graphene\n"
                "import graphene_django\n"
                "from graphene import relay\n"
                "\n"
                "\n"
                "# ------------------------------------------------------------------\n"
                "# Sample Relay Node\n"
                "# ------------------------------------------------------------------\n"
                "\n"
                "\n"
                "class SampleNode(relay.Node):\n"
                '    """Example Relay node.  Replace with your own models."""\n'
                "\n"
                "    class Meta:\n"
                '        name = "Sample"\n'
                "\n"
                "    @classmethod\n"
                "    def get_node(cls, info, id):\n"
                "        # TODO: Replace with actual model query\n"
                "        # e.g. return MyModel.objects.get(pk=id)\n"
                "        return None\n"
                "\n"
                "\n"
                "# ------------------------------------------------------------------\n"
                "# Query root\n"
                "# ------------------------------------------------------------------\n"
                "\n"
                "\n"
                "class Query(graphene.ObjectType):\n"
                '    """Root query type.\n'
                "\n"
                "    Add your own fields here.  Example::\n"
                "\n"
                "        my_models = graphene.List(MyModelNode)\n"
                "\n"
                "        def resolve_my_models(self, info, **kwargs):\n"
                "            return MyModel.objects.all()\n"
                '    """\n'
                "\n"
                '    health = graphene.String(default_value="ok")\n'
                '    """Simple health-check field.  Always returns ``"ok"``."""\n'
                "\n"
                "    # TODO: Add your query fields here\n"
                "    # sample = relay.Node.Field(SampleNode)\n"
                "\n"
                "\n"
                "# ------------------------------------------------------------------\n"
                "# Schema\n"
                "# ------------------------------------------------------------------\n"
                "\n"
                "schema = graphene.Schema(query=Query)\n"
            )
            (pkg / "schema.py").write_text(schema_content)

            # ── 4. Update urls.py ────────────────────────────────────────
            urls_path = pkg / "urls.py"
            urls_content = (
                '"""\n'
                f"URL configuration for {project_name} project.\n"
                '"""\n'
                "from django.contrib import admin\n"
                "from django.urls import path\n"
                "from graphene_django.views import GraphQLView\n"
                "from django.views.decorators.csrf import csrf_exempt\n"
                "\n"
                "urlpatterns = [\n"
                "    path('admin/', admin.site.urls),\n"
                "    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=True)),\n"
                "         name='graphql'),\n"
                "]\n"
            )
            urls_path.write_text(urls_content)

        except OSError as exc:
            raise PresetError(
                f"Failed to write GraphQL API preset files: {exc}"
            ) from exc

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _default_settings(
        project_name: str,
        db_type: str,
        db_config: dict[str, Any],
    ) -> str:
        """Return a minimal settings.py (fallback)."""
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
            "    # ── GraphQL ────────────────────────────────\n"
            "    'graphene_django',\n"
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
            "\n"
            "# ============================================================\n"
            "# GRAPHQL CONFIGURATION\n"
            "# ============================================================\n"
            "GRAPHENE = {\n"
            f"    'SCHEMA': '{project_name}.schema.schema',\n"
            "    'MIDDLEWARE': [\n"
            "        'graphene_django.debug.DjangoDebugMiddleware',\n"
            "    ],\n"
            "}\n"
        )
