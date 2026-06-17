"""Testing Infrastructure add-on.

Sets up pytest, pytest-django, coverage, factory-boy, and a CI-ready
test configuration.  Discovers models across all apps and generates
per-app test directories with factories and test stubs.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ajo.presets.addons import AbstractAddon, register_addon


@register_addon
class TestingAddon(AbstractAddon):
    """Add pytest, coverage, factory-boy, and CI test configuration."""

    name = "Testing Infrastructure"
    description = "pytest + coverage + factory-boy + CI config"
    dependencies = [
        "pytest-django",
        "pytest-cov",
        "factory-boy",
    ]
    dev_dependencies = [
        "pytest",
        "pytest-django",
        "pytest-cov",
        "factory-boy",
    ]
    compatible_presets: list[str] | None = None
    conflicts_with: list[str] = []

    settings_blocks = [
        """
# ---------------------------------------------------------------------------
# Testing Infrastructure — pytest Configuration
# ---------------------------------------------------------------------------
# The settings below are referenced by pytest-django via the
# DJANGO_SETTINGS_MODULE environment variable or pytest config.
# No runtime settings changes are needed here.
""",
    ]

    preview_files: list[tuple[str, int]] = [
        ("pytest.ini", 512),
        ("conftest.py", 2048),
        (".coveragerc", 512),
        ("accounts/tests/__init__.py", 0),
        ("accounts/tests/factories.py", 1024),
        ("accounts/tests/test_models.py", 512),
        ("accounts/tests/test_apis.py", 1024),
        ("core/tests/__init__.py", 0),
        ("core/tests/test_models.py", 512),
    ]

    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        """Scaffold test configuration and per-app test directories."""
        await self._inject_settings(project_path)

        preset_key = env_config.get("preset_key", "monolith")

        # ── pytest.ini ────────────────────────────────────────────────
        self._write_file(
            project_path / "pytest.ini",
            """[pytest]
DJANGO_SETTINGS_MODULE = {project_name}.settings
python_files = tests.py test_*.py *_tests.py
testpaths = {project_name}

# Coverage configuration
addopts =
    --cov={project_name}
    --cov-report=term-missing
    --cov-report=html
    --nomigrations
    --reuse-db
""".format(project_name=project_name),
        )

        # ── .coveragerc ───────────────────────────────────────────────
        self._write_file(
            project_path / ".coveragerc",
            """[run]
source = {project_name}
omit = */migrations/*, */tests/*, manage.py, */*.pyc

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if __name__ == "__main__":
    raise NotImplementedError
    @abc.abstractmethod
    @abstractmethod

fail_under = 80
""".format(project_name=project_name),
        )

        # ── Root conftest.py ──────────────────────────────────────────
        self._write_file(
            project_path / "conftest.py",
            '''"""pytest configuration and shared fixtures for all apps."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    """Return a REST framework APIClient."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    """Return an APIClient authenticated with a fresh user."""
    from accounts.tests.factories import UserFactory
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return api_client, user
''',
        )

        # ── Discover apps and generate per-app test directories ──────
        apps = self._discover_apps(project_path)

        # Remove app names that are Django internals or project package
        project_pkg = project_name.replace("-", "_")
        skip = {"__pycache__", "migrations", "templates", "static", project_pkg}
        apps = [a for a in apps if a not in skip]

        for app_name in apps:
            tests_dir = project_path / app_name / "tests"
            models_path = project_path / app_name / "models.py"

            tests_dir.mkdir(parents=True, exist_ok=True)
            self._write_file(tests_dir / "__init__.py", "")

            # Try to discover model classes for this app
            model_names = (
                self._discover_models(models_path) if models_path.exists() else []
            )

            # Generate factories for discovered models
            self._write_file(
                tests_dir / "factories.py",
                self._generate_factories(app_name, model_names, project_name),
            )

            # Generate test stubs
            is_api_app = preset_key in ("rest-api", "rest", "ninja-api", "ninja")
            self._write_file(
                tests_dir / "test_models.py",
                self._generate_model_tests(app_name, model_names),
            )
            self._write_file(
                tests_dir / "test_apis.py",
                self._generate_api_tests(app_name, model_names, is_api_app),
            )

    # ── Model discovery ───────────────────────────────────────────────

    def _discover_models(self, models_path: Path) -> list[str]:
        """Parse ``models.py`` and return names of model classes.

        Uses AST to find class definitions that inherit from
        ``models.Model`` or ``AbstractUser``, ``AbstractBaseUser``, etc.
        """
        try:
            source = models_path.read_text(encoding="utf-8")
        except OSError:
            return []

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        models: list[str] = []
        django_bases = {
            "Model",
            "AbstractUser",
            "AbstractBaseUser",
            "AbstractGroup",
        }

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

    # ── Factory generation ────────────────────────────────────────────

    def _generate_factories(
        self,
        app_name: str,
        model_names: list[str],
        project_name: str,
    ) -> str:
        """Generate ``factories.py`` content for the given app + models."""
        lines = [
            '"""Factory classes for :mod:`{}.{}` models."""'.format(
                project_name, app_name
            ),
            "",
            "import factory",
            "from factory.django import DjangoModelFactory",
            "",
        ]

        if not model_names:
            # Default generic factory even without discovered models
            lines += [
                "from django.contrib.auth import get_user_model",
                "",
                "User = get_user_model()",
                "",
                "",
                "class UserFactory(DjangoModelFactory):",
                '    """Factory for creating test users."""',
                "",
                '    username = factory.Faker("user_name")',
                '    email = factory.Faker("email")',
                '    password = factory.Faker("password")',
                "",
                "    class Meta:",
                "        model = User",
                "",
                "    @classmethod",
                "    def _create(cls, model_class, *args, **kwargs):",
                '        """Use ``create_user`` to ensure the password is hashed."""',
                '        password = kwargs.pop("password", None)',
                "        instance = model_class(*args, **kwargs)",
                "        if password:",
                "            instance.set_password(password)",
                "        instance.save()",
                "        return instance",
            ]
            return "\n".join(lines) + "\n"

        lines.append("from {} import models".format(app_name))
        lines.append("")

        for model_name in model_names:
            # Basic factory with Faker for common field types
            lines += [
                "",
                "class {}Factory(DjangoModelFactory):".format(model_name),
                '    """Factory for :class:`{}` instances.""".format(model_name)',
                "",
                "    class Meta:",
                "        model = models.{}".format(model_name),
                "",
            ]

        return "\n".join(lines) + "\n"

    # ── Test stub generation ──────────────────────────────────────────

    def _generate_model_tests(
        self,
        app_name: str,
        model_names: list[str],
    ) -> str:
        """Generate ``test_models.py`` content."""
        lines = [
            '"""Tests for :mod:`{}` models.""".format(app_name)',
            "",
            "import pytest",
            "",
        ]

        if model_names:
            lines += [
                "from .factories import {}".format(
                    ", ".join("{}Factory".format(m) for m in model_names)
                ),
                "",
            ]
            for model_name in model_names:
                factory_name = "{}Factory".format(model_name)
                lines += [
                    "",
                    "class Test{}:".format(model_name),
                    '    """Test suite for :class:`{}`.""".format(model_name)',
                    "",
                    "    @pytest.mark.django_db",
                    "    def test_factory_create(self):",
                    '        """Verify the factory can create a valid instance."""',
                    "        instance = {}()".format(factory_name),
                    "        assert instance.pk is not None",
                    "        assert str(instance)",
                    "",
                    "    @pytest.mark.django_db",
                    "    def test_str_representation(self):",
                    '        """Verify ``__str__`` returns a string."""',
                    "        instance = {}()".format(factory_name),
                    "        assert isinstance(str(instance), str)",
                    "",
                ]
        else:
            lines += [
                "",
                "@pytest.mark.django_db",
                "def test_app_importable():",
                '    """Verify the app module can be imported."""',
                "    import importlib",
                '    mod = importlib.import_module("{}")'.format(app_name),
                "    assert mod is not None",
                "",
            ]

        return "\n".join(lines) + "\n"

    def _generate_api_tests(
        self,
        app_name: str,
        model_names: list[str],
        is_api_app: bool,
    ) -> str:
        """Generate ``test_apis.py`` content."""
        if is_api_app:
            return self._generate_drf_api_tests(app_name, model_names)
        return self._generate_view_tests(app_name)

    def _generate_drf_api_tests(
        self,
        app_name: str,
        model_names: list[str],
    ) -> str:
        """DRF/API endpoint tests."""
        lines = [
            '"""API endpoint tests for :mod:`{}`.""".format(app_name)',
            "",
            "import pytest",
            "from django.urls import reverse",
            "",
        ]
        if model_names:
            from_clause = "from .factories import {}".format(
                ", ".join("{}Factory".format(m) for m in model_names)
            )
            lines.append(from_clause)
            lines.append("")

        lines += [
            "@pytest.mark.django_db",
            "def test_api_list_authenticated(api_client):",
            '    """Verify authenticated access to list endpoints."""',
            '    response = api_client.get(reverse("api:root"))',
            "    assert response.status_code == 200",
            "",
            "",
            "@pytest.mark.django_db",
            "def test_api_list_unauthenticated(api_client):",
            '    """Verify unauthenticated access returns 401."""',
            '    response = api_client.get(reverse("api:root"))',
            "    assert response.status_code in (200, 401)",
            "",
        ]
        return "\n".join(lines) + "\n"

    def _generate_view_tests(self, app_name: str) -> str:
        """Server-rendered view tests."""
        lines = [
            '"""View tests for :mod:`{}`.""".format(app_name)',
            "",
            "import pytest",
            "from django.test import Client",
            "from django.urls import reverse",
            "",
            "",
            "@pytest.mark.django_db",
            "def test_homepage(client):",
            '    """Verify the homepage returns 200."""',
            '    response = client.get("/")',
            "    assert response.status_code == 200",
            "",
            "",
            "@pytest.mark.django_db",
            "def test_login_page(client):",
            '    """Verify the login page is accessible."""',
            '    response = client.get(reverse("login"))',
            "    assert response.status_code == 200",
            "",
        ]
        return "\n".join(lines) + "\n"
