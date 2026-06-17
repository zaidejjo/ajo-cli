"""Docker Sync Engine — dynamic docker-compose.yml generation.

Synchronises the database choice from ``ajo.database_manager.DatabaseManager``
directly into production-ready ``docker-compose.yml`` manifests with:

* Health checks for PostgreSQL, MySQL, Redis.
* Dependency graph (web → db/redis, optional celery → db/redis).
* Redis cache service (always included).
* Optional Celery worker service.

Usage::

    from ajo.presets.docker_sync import DockerSyncEngine

    compose_yaml = DockerSyncEngine.generate_compose(
        project_name="myapp",
        db_type="postgresql",
        include_celery=True,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from ajo.core.exceptions import PresetError


# ── Data containers ─────────────────────────────────────────────────────────


@dataclass
class DockerServiceConfig:
    """Configuration for a single Docker Compose service.

    Attributes:
        image: Docker image tag (e.g. ``"postgres:16-alpine"``).
        container_name: Service container name.
        restart: Restart policy (default ``"unless-stopped"``).
        ports: List of port mappings (e.g. ``["5432:5432"]``).
        volumes: List of volume mounts.
        environment: Dict of environment variables.
        healthcheck: Health check configuration dict with keys ``test``,
            ``interval``, ``timeout``, ``retries``, ``start_period``.
        depends_on: List of service names this service depends on.
        command: Override command for the container.
    """

    image: str
    container_name: str
    restart: str = "unless-stopped"
    ports: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    healthcheck: dict[str, Any] | None = None
    depends_on: list[str] = field(default_factory=list)
    command: str | None = None


# ── Sync Engine ─────────────────────────────────────────────────────────────


class DockerSyncEngine:
    """Docker Compose blueprint engine synchronised with database config.

    .. rubric:: Service topology

    ::

        ┌─────────┐     depends_on (healthy)     ┌──────────┐
        │   web   │ ────────────────────────────▶ │  redis   │
        └────┬────┘                               └──────────┘
             │
             │  depends_on (healthy)
             ▼
        ┌──────────┐
        │    db    │  (postgres │ mysql)
        └──────────┘

        (optional)
        ┌──────────┐     depends_on (healthy)     ┌──────────┐
        │  celery  │ ────────────────────────────▶ │  redis   │
        └──────────┘                               │    db    │
                                                   └──────────┘
    """

    #: Database service blueprints keyed by ``db_type``.
    DB_SERVICE_MAP: Final[dict[str, DockerServiceConfig]] = {
        "postgresql": DockerServiceConfig(
            image="postgres:16-alpine",
            container_name="db",
            ports=["5432:5432"],
            volumes=["postgres_data:/var/lib/postgresql/data"],
            healthcheck={
                "test": ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"],
                "interval": "5s",
                "timeout": "3s",
                "retries": 5,
                "start_period": "10s",
            },
        ),
        "mysql": DockerServiceConfig(
            image="mysql:8.0",
            container_name="db",
            ports=["3306:3306"],
            volumes=["mysql_data:/var/lib/mysql"],
            environment={"MYSQL_ROOT_PASSWORD": "${DB_PASSWORD:-root}"},
            healthcheck={
                "test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
                "interval": "5s",
                "timeout": "3s",
                "retries": 5,
                "start_period": "10s",
            },
        ),
    }

    #: Redis service blueprint (always included).
    REDIS_SERVICE: Final[DockerServiceConfig] = DockerServiceConfig(
        image="redis:7-alpine",
        container_name="redis",
        ports=["6379:6379"],
        volumes=["redis_data:/data"],
        healthcheck={
            "test": ["CMD", "redis-cli", "ping"],
            "interval": "5s",
            "timeout": "3s",
            "retries": 5,
        },
    )

    #: Mailhog service blueprint (always included for dev).
    MAILHOG_SERVICE: Final[DockerServiceConfig] = DockerServiceConfig(
        image="mailhog/mailhog:latest",
        container_name="mailhog",
        ports=["8025:8025", "1025:1025"],
    )

    # ── Public generation API ────────────────────────────────────────────

    @classmethod
    def generate_compose(
        cls,
        project_name: str,
        db_type: str,
        *,
        include_celery: bool = False,
    ) -> str:
        """Generate a complete ``docker-compose.yml`` manifest.

        Args:
            project_name: Project name used in file header comments.
            db_type: Database type key (e.g. ``"postgresql"``, ``"mysql"``).
            include_celery: If ``True``, include a Celery worker service.

        Returns:
            A complete ``docker-compose.yml`` string.

        Raises:
            PresetError: If *db_type* is unsupported and no fallback
                is available.
        """
        lines: list[str] = [
            "# ============================================================",
            f"# docker-compose.yml — {project_name}",
            "# Generated by AJO CLI DockerSyncEngine",
            "# ============================================================",
            "",
            'version: "3.9"',
            "",
            "services:",
            "",
        ]

        # ── Web service ──────────────────────────────────────────────
        web_depends: list[str] = []
        if db_type in cls.DB_SERVICE_MAP:
            web_depends.append("db:condition:service_healthy")
        web_depends.append("redis:condition:service_started")

        lines.append("  # ── Django Web Application ───────────────────")
        lines.append("  web:")
        lines.append("    build: .")
        lines.append("    restart: unless-stopped")
        lines.append("    ports:")
        lines.append('      - "8000:8000"')
        lines.append("    env_file:")
        lines.append("      - .env")
        lines.append("    environment:")
        if db_type in cls.DB_SERVICE_MAP:
            lines.append("      DB_HOST: db")
        lines.append("    depends_on:")
        for dep in web_depends:
            svc, _, cond = dep.partition(":")
            lines.append(f"      {svc}:")
            lines.append(f"        condition: {cond}")
        lines.append("    volumes:")
        lines.append("      - .:/app")
        lines.append(
            "    command: /app/.venv/bin/python manage.py runserver 0.0.0.0:8000"
        )
        lines.append("")

        # ── Database service ─────────────────────────────────────────
        if db_type in cls.DB_SERVICE_MAP:
            db_cfg = cls.DB_SERVICE_MAP[db_type]
            cls._append_service(lines, db_cfg)
            lines.append("")

        # ── Redis service ────────────────────────────────────────────
        cls._append_service(lines, cls.REDIS_SERVICE)
        lines.append("")

        # ── Mailhog service ──────────────────────────────────────────
        cls._append_service(lines, cls.MAILHOG_SERVICE)
        lines.append("")

        # ── Optional Celery worker ───────────────────────────────────
        if include_celery:
            celery_depends = ["redis:condition:service_healthy"]
            if db_type in cls.DB_SERVICE_MAP:
                celery_depends.append("db:condition:service_healthy")

            lines.append("  # ── Celery Worker ─────────────────────────────")
            lines.append("  celery:")
            lines.append("    build: .")
            lines.append("    restart: unless-stopped")
            lines.append("    env_file:")
            lines.append("      - .env")
            lines.append("    environment:")
            if db_type in cls.DB_SERVICE_MAP:
                lines.append("      DB_HOST: db")
            lines.append("    depends_on:")
            for dep in celery_depends:
                svc, _, cond = dep.partition(":")
                lines.append(f"      {svc}:")
                lines.append(f"        condition: {cond}")
            lines.append(
                "    command: /app/.venv/bin/python -m celery -A ${CELERY_APP_NAME:-config} worker -l info"
            )
            lines.append("")

        # ── Volumes ─────────────────────────────────────────────────
        volumes: list[str] = []
        if db_type in cls.DB_SERVICE_MAP:
            db_cfg = cls.DB_SERVICE_MAP[db_type]
            for vol in db_cfg.volumes:
                vol_name = vol.split(":")[0]
                if vol_name not in volumes:
                    volumes.append(vol_name)
        volumes.append("redis_data")

        lines.append("volumes:")
        for vol_name in volumes:
            lines.append(f"  {vol_name}:")

        return "\n".join(lines) + "\n"

    # ── Internal helpers ──────────────────────────────────────────────

    @classmethod
    def _append_service(cls, lines: list[str], cfg: DockerServiceConfig) -> None:
        """Append a Docker Compose service block to *lines*."""
        lines.append(f"  # ── {cfg.container_name.capitalize()} Service ────────")
        lines.append(f"  {cfg.container_name}:")
        lines.append(f"    image: {cfg.image}")
        lines.append(f"    restart: {cfg.restart}")

        if cfg.ports:
            lines.append("    ports:")
            for p in cfg.ports:
                lines.append(f'      - "{p}"')

        if cfg.volumes:
            lines.append("    volumes:")
            for v in cfg.volumes:
                lines.append(f"      - {v}")

        if cfg.environment:
            lines.append("    environment:")
            for k, v in cfg.environment.items():
                lines.append(f"      {k}: {v}")

        if cfg.healthcheck is not None:
            lines.append("    healthcheck:")
            cls._append_healthcheck(lines, cfg.healthcheck)

        if cfg.depends_on:
            lines.append("    depends_on:")
            for dep in cfg.depends_on:
                lines.append(f"      - {dep}")

        if cfg.command is not None:
            lines.append(f"    command: {cfg.command}")

    @staticmethod
    def _append_healthcheck(lines: list[str], hc: dict[str, Any]) -> None:
        """Append a health check block to *lines*."""
        test = hc.get("test", ["CMD-SLEEP", "true"])
        # Format healthcheck test properly
        if isinstance(test, list):
            test_str = str(test).replace("'", '"')
            lines.append(f"      test: {test_str}")
        else:
            lines.append(f'      test: ["CMD-SHELL", "{test}"]')

        interval = hc.get("interval", "30s")
        timeout = hc.get("timeout", "10s")
        retries = hc.get("retries", 3)
        start_period = hc.get("start_period")

        lines.append(f"      interval: {interval}")
        lines.append(f"      timeout: {timeout}")
        lines.append(f"      retries: {retries}")
        if start_period is not None:
            lines.append(f"      start_period: {start_period}")

    @classmethod
    def get_db_service(cls, db_type: str) -> DockerServiceConfig | None:
        """Return the :class:`DockerServiceConfig` for a given *db_type*.

        Returns ``None`` for SQLite (no external DB service needed).
        """
        return cls.DB_SERVICE_MAP.get(db_type)

    @classmethod
    def is_supported(cls, db_type: str) -> bool:
        """Check whether *db_type* has a Docker service blueprint."""
        return db_type in cls.DB_SERVICE_MAP
