"""Shared fixtures and sample data for add-on system tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest

# ── Sample settings.py (representative of a scaffolded Django project) ──

SAMPLE_SETTINGS = """from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'dummy-secret-key-not-for-production'
DEBUG = True
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
"""

SAMPLE_ENV = """SECRET_KEY=dummy
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_TYPE=sqlite
"""

SAMPLE_URLS = """from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
]
"""

SAMPLE_MODELS = """from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    body = models.TextField()
    rating = models.IntegerField(default=5)

    def __str__(self):
        return f'Review {self.id} for {self.product.name}'


class NotAModel:
    pass
"""


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_settings() -> str:
    """Return a canonical sample ``settings.py`` for injection tests."""
    return SAMPLE_SETTINGS


@pytest.fixture
def sample_env() -> str:
    """Return a sample ``.env`` content."""
    return SAMPLE_ENV


@pytest.fixture
def sample_urls() -> str:
    """Return a sample ``urls.py`` content."""
    return SAMPLE_URLS


@pytest.fixture
def sample_models() -> str:
    """Return sample ``models.py`` for model discovery tests."""
    return SAMPLE_MODELS


@pytest.fixture
def temp_project():
    """Create a temporary project directory with a Django-like structure.

    Yields the path to the temp directory.
    Cleaned up automatically after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir(parents=True)

        # Create a Django project package
        pkg = project_path / "config"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "settings.py").write_text(SAMPLE_SETTINGS)
        (pkg / "urls.py").write_text(SAMPLE_URLS)

        # Create a Django app
        app_dir = project_path / "products"
        app_dir.mkdir()
        (app_dir / "__init__.py").write_text("")
        (app_dir / "apps.py").write_text(
            "from django.apps import AppConfig\n\n"
            "class ProductsConfig(AppConfig):\n"
            '    name = "products"\n'
        )
        (app_dir / "models.py").write_text(SAMPLE_MODELS)

        # Create .env
        (project_path / ".env").write_text(SAMPLE_ENV)

        yield project_path


@pytest.fixture
def env_config() -> dict:
    """Return a minimal env_config dict for add-on apply() calls."""
    return {
        "project_name": "test_project",
        "db_type": "sqlite",
        "db_config": {},
        "preset_key": "monolith",
    }


@pytest.fixture
def env_config_rest() -> dict:
    """Return env_config with REST API preset."""
    return {
        "project_name": "test_project",
        "db_type": "sqlite",
        "db_config": {},
        "preset_key": "rest-api",
    }


@pytest.fixture
def env_config_ninja() -> dict:
    """Return env_config with Ninja API preset."""
    return {
        "project_name": "test_project",
        "db_type": "sqlite",
        "db_config": {},
        "preset_key": "ninja-api",
    }


@pytest.fixture
def registered_addon_keys() -> list[str]:
    """Return the list of expected add-on registry keys."""
    return ["auth", "cache", "security", "testing"]
