"""Standard Monolith preset — traditional Django with Bootstrap 5 templates.

This is the default architecture preset.  It generates:
- A standard Django project structure (``manage.py``, settings, URLs, etc.)
- Bootstrap 5 HTML template base
- ``python-dotenv`` for environment configuration
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.core.exceptions import PresetError
from ajo.presets.base import AbstractPreset
from ajo.presets import register


@register
class MonolithPreset(AbstractPreset):
    """Traditional Django project with Bootstrap 5 templates."""

    @classmethod
    def registry_key(cls) -> str:
        return "monolith"

    @property
    def name(self) -> str:
        return "Standard Monolith"

    @property
    def description(self) -> str:
        return "Traditional Django with Bootstrap 5 templates"

    @property
    def dependencies(self) -> list[str]:
        return ["django", "python-dotenv"]

    @property
    def dev_dependencies(self) -> list[str]:
        return ["ruff"]

    @property
    def preview_files(self) -> list[tuple[str, int]]:
        return [
            ("manage.py", 2048),
            ("__init__.py", 64),  # project package (/project_name/)
            ("settings.py", 4096),
            ("urls.py", 512),
            ("wsgi.py", 256),
            ("asgi.py", 256),
            ("templates/base.html", 2048),
        ]

    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold a standard Django project.

        Creates the full Django project structure including ``manage.py``,
        the project package, settings, URL configuration, ASGI/WSGI entry
        points, environment configuration, and Bootstrap 5 templates.
        """
        project_name: str = env_config["project_name"]
        db_config: dict[str, Any] = env_config.get("db_config", {})
        db_type: str = env_config.get("db_type", "sqlite")

        try:
            # ── Create manage.py ────────────────────────────────────────
            manage_py = (
                "#!/usr/bin/env python\n"
                '"""Django\'s command-line utility for administrative tasks."""\n'
                "import os\n"
                "import sys\n"
                "\n"
                "def main():\n"
                '    """Run administrative tasks."""\n'
                f"    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{project_name}.settings')\n"
                "    try:\n"
                "        from django.core.management import execute_from_command_line\n"
                "    except ImportError as exc:\n"
                "        raise ImportError(\n"
                '            "Couldn\'t import Django."\n'
                "        ) from exc\n"
                "    execute_from_command_line(sys.argv)\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            )
            (project_path / "manage.py").write_text(manage_py)

            # ── Project package ──────────────────────────────────────────
            pkg = project_path / project_name
            pkg.mkdir(exist_ok=True)

            (pkg / "__init__.py").write_text("")

            # ── asgi.py ──────────────────────────────────────────────────
            asgi_py = (
                '"""\n'
                f"ASGI config for {project_name} project.\n"
                '"""\n'
                "import os\n"
                "from django.core.asgi import get_asgi_application\n"
                "\n"
                f"os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{project_name}.settings')\n"
                "application = get_asgi_application()\n"
            )
            (pkg / "asgi.py").write_text(asgi_py)

            # ── wsgi.py ──────────────────────────────────────────────────
            wsgi_py = (
                '"""\n'
                f"WSGI config for {project_name} project.\n"
                '"""\n'
                "import os\n"
                "from django.core.wsgi import get_wsgi_application\n"
                "\n"
                f"os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{project_name}.settings')\n"
                "application = get_wsgi_application()\n"
            )
            (pkg / "wsgi.py").write_text(wsgi_py)

            # ── urls.py ──────────────────────────────────────────────────
            urls_py = (
                '"""\n'
                f"URL configuration for {project_name} project.\n"
                '"""\n'
                "from django.contrib import admin\n"
                "from django.urls import path, include\n"
                "\n"
                "urlpatterns = [\n"
                "    path('admin/', admin.site.urls),\n"
                "]\n"
            )
            (pkg / "urls.py").write_text(urls_py)

            # ── settings.py ──────────────────────────────────────────────
            settings_py = self._build_settings(project_name, db_type, db_config)
            (pkg / "settings.py").write_text(settings_py)

            # ── Templates directory with Bootstrap 5 base ────────────────
            templates_dir = project_path / "templates"
            templates_dir.mkdir(exist_ok=True)

            base_html = (
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "<head>\n"
                '    <meta charset="UTF-8">\n'
                '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                "    <title>{% block title %}AJO Django{% endblock %}</title>\n"
                '    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">\n'
                "    <style>\n"
                "        body {\n"
                "            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);\n"
                "            min-height: 100vh;\n"
                "        }\n"
                "        .main-card {\n"
                "            background: white;\n"
                "            border-radius: 20px;\n"
                "            padding: 2rem;\n"
                "            margin: 2rem 0;\n"
                "            box-shadow: 0 10px 40px rgba(0,0,0,0.1);\n"
                "        }\n"
                "    </style>\n"
                "</head>\n"
                "<body>\n"
                '    <nav class="navbar navbar-dark bg-dark">\n'
                '        <div class="container">\n'
                '            <a class="navbar-brand" href="/">⚡ AJO Django</a>\n'
                "        </div>\n"
                "    </nav>\n"
                '    <div class="container">\n'
                '        <div class="main-card">\n'
                "            {% block content %}\n"
                '            <div class="text-center">\n'
                "                <h1>Welcome to Your Django Project</h1>\n"
                "                <p>Powered by AJO CLI</p>\n"
                '                <a href="/admin" class="btn btn-primary">Admin Panel</a>\n'
                "            </div>\n"
                "            {% endblock %}\n"
                "        </div>\n"
                "    </div>\n"
                "</body>\n"
                "</html>\n"
            )
            (templates_dir / "base.html").write_text(base_html)

        except OSError as exc:
            raise PresetError(f"Failed to write monolith project files: {exc}") from exc

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _build_settings(
        project_name: str,
        db_type: str,
        db_config: dict[str, Any],
    ) -> str:
        """Build the content of ``settings.py``."""
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


# ── Module-level helpers (shared with other presets) ────────────────────────


def _render_db_block(db_type: str, db_config: dict[str, Any]) -> str:
    """Render the ``DATABASES`` settings block for the given database type."""
    if db_type == "sqlite":
        return (
            "DATABASES = {\n"
            "    'default': {\n"
            "        'ENGINE': 'django.db.backends.sqlite3',\n"
            "        'NAME': BASE_DIR / 'db.sqlite3',\n"
            "    }\n"
            "}\n"
        )

    if db_type == "postgresql":
        name = db_config.get("name", "postgres")
        user = db_config.get("user", "postgres")
        password = db_config.get("password", "")
        host = db_config.get("host", "localhost")
        port = db_config.get("port", "5432")
        return (
            "DATABASES = {\n"
            "    'default': {\n"
            "        'ENGINE': 'django.db.backends.postgresql',\n"
            f"        'NAME': os.getenv('DB_NAME', '{name}'),\n"
            f"        'USER': os.getenv('DB_USER', '{user}'),\n"
            f"        'PASSWORD': os.getenv('DB_PASSWORD', '{password}'),\n"
            f"        'HOST': os.getenv('DB_HOST', '{host}'),\n"
            f"        'PORT': os.getenv('DB_PORT', '{port}'),\n"
            "    }\n"
            "}\n"
        )

    if db_type == "mysql":
        name = db_config.get("name", "mysql")
        user = db_config.get("user", "root")
        password = db_config.get("password", "")
        host = db_config.get("host", "localhost")
        port = db_config.get("port", "3306")
        return (
            "DATABASES = {\n"
            "    'default': {\n"
            "        'ENGINE': 'django.db.backends.mysql',\n"
            f"        'NAME': os.getenv('DB_NAME', '{name}'),\n"
            f"        'USER': os.getenv('DB_USER', '{user}'),\n"
            f"        'PASSWORD': os.getenv('DB_PASSWORD', '{password}'),\n"
            f"        'HOST': os.getenv('DB_HOST', '{host}'),\n"
            f"        'PORT': os.getenv('DB_PORT', '{port}'),\n"
            "        'OPTIONS': {\n"
            "            'init_command': \"SET sql_mode='STRICT_TRANS_TABLES'\",\n"
            "            'charset': 'utf8mb4',\n"
            "        },\n"
            "    }\n"
            "}\n"
        )

    return ""
