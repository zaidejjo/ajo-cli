"""Database configuration management."""

from pathlib import Path
from typing import Dict, Tuple
from rich.console import Console

console = Console()


class DatabaseManager:
    """Handle database configuration and package installation."""

    DATABASE_CONFIGS = {
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
        },
    }

    @staticmethod
    def get_config(db_type: str, config: Dict) -> Dict:
        """Get database configuration."""
        base_config = DatabaseManager.DATABASE_CONFIGS.get(db_type, {})
        return {**base_config, **config}
