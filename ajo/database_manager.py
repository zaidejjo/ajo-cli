"""Database configuration management with Docker sync metadata.

Each database entry now includes ``docker_service`` metadata consumed by
:class:`~ajo.presets.docker_sync.DockerSyncEngine` for auto-generating
production-ready ``docker-compose.yml`` manifests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


class DatabaseManager:
    """Handle database configuration and package installation.

    .. rubric:: Docker sync metadata

    Each database config (except SQLite) now carries a ``docker_service``
    key whose value is a dict consumed by ``DockerSyncEngine``:

    .. code-block:: python

        {
            "image": "postgres:16-alpine",
            "healthcheck": "pg_isready",
            "port": "5432",
            "volume": "postgres_data:/var/lib/postgresql/data",
        }
    """

    DATABASE_CONFIGS: dict[str, dict[str, Any]] = {
        "sqlite": {
            "engine": "django.db.backends.sqlite3",
            "packages": [],
            "template": """
DATABASES = {{
    'default': {{
        'ENGINE': '{engine}',
        'NAME': BASE_DIR / '{name}',
    }}
}}
""",
            "docker_service": None,  # SQLite needs no external service
        },
        "postgresql": {
            "engine": "django.db.backends.postgresql",
            "packages": ["psycopg2-binary"],
            "template": """
DATABASES = {{
    'default': {{
        'ENGINE': '{engine}',
        'NAME': '{name}',
        'USER': '{user}',
        'PASSWORD': '{password}',
        'HOST': '{host}',
        'PORT': '{port}',
    }}
}}
""",
            "docker_service": {
                "image": "postgres:16-alpine",
                "healthcheck": "pg_isready",
                "port": "5432",
                "volume": "postgres_data:/var/lib/postgresql/data",
                "env": {
                    "POSTGRES_DB": "${DB_NAME:-postgres}",
                    "POSTGRES_USER": "${DB_USER:-postgres}",
                    "POSTGRES_PASSWORD": "${DB_PASSWORD:-postgres}",
                },
            },
        },
        "mysql": {
            "engine": "django.db.backends.mysql",
            "packages": ["mysqlclient"],
            "template": """
DATABASES = {{
    'default': {{
        'ENGINE': '{engine}',
        'NAME': '{name}',
        'USER': '{user}',
        'PASSWORD': '{password}',
        'HOST': '{host}',
        'PORT': '{port}',
        'OPTIONS': {{
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }},
    }}
}}
""",
            "docker_service": {
                "image": "mysql:8.0",
                "healthcheck": "mysqladmin ping",
                "port": "3306",
                "volume": "mysql_data:/var/lib/mysql",
                "env": {
                    "MYSQL_ROOT_PASSWORD": "${DB_PASSWORD:-root}",
                },
            },
        },
    }

    @staticmethod
    def get_config(db_type: str, config: dict[str, Any]) -> dict[str, Any]:
        """Get database configuration merged with overrides.

        Args:
            db_type: One of ``"sqlite"``, ``"postgresql"``, ``"mysql"``.
            config: Override dict that will be merged on top of the
                base configuration.

        Returns:
            A merged configuration dict.
        """
        base_config = DatabaseManager.DATABASE_CONFIGS.get(db_type, {})
        merged: dict[str, Any] = {**base_config, **config}
        return merged

    @staticmethod
    def get_docker_service(db_type: str) -> dict[str, Any] | None:
        """Return Docker service metadata for a database type.

        Args:
            db_type: Database type key.

        Returns:
            A dict with ``image``, ``healthcheck``, ``port``, and
            ``volume`` keys, or ``None`` for SQLite.
        """
        cfg = DatabaseManager.DATABASE_CONFIGS.get(db_type, {})
        return cfg.get("docker_service")

    @staticmethod
    def list_databases() -> list[str]:
        """Return the list of supported database type keys."""
        return list(DatabaseManager.DATABASE_CONFIGS.keys())

    @staticmethod
    def supports_docker(db_type: str) -> bool:
        """Check whether *db_type* has a Docker service definition.

        Returns ``False`` for SQLite (file-based, no external service).
        """
        svc = DatabaseManager.get_docker_service(db_type)
        return svc is not None
