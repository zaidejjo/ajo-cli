"""Dockerization preset — multi-stage Dockerfile + docker-compose.

This preset generates:
- A multi-stage ``Dockerfile`` that leverages ``uv`` package caching
  for fast rebuilds in CI.
- A ``docker-compose.yml`` wired with PostgreSQL, Redis, and Mailhog.
- A ``.dockerignore`` for optimal build context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ajo.core.exceptions import PresetError
from ajo.presets import register
from ajo.presets.base import AbstractPreset


@register
class DockerPreset(AbstractPreset):
    """Multi-stage Dockerfile + docker-compose with PostgreSQL, Redis, Mailhog."""

    @classmethod
    def registry_key(cls) -> str:
        return "docker"

    @property
    def name(self) -> str:
        return "Docker"

    @property
    def description(self) -> str:
        return "Multi-stage Dockerfile + Compose with PostgreSQL, Redis, Mailhog"

    @property
    def dependencies(self) -> list[str]:
        return []

    @property
    def dev_dependencies(self) -> list[str]:
        return []

    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Generate Docker infrastructure files into *project_path*.

        Creates:
        * ``Dockerfile`` — multi-stage build with ``uv`` cache.
        * ``docker-compose.yml`` — web service + PostgreSQL + Redis + Mailhog.
        * ``.dockerignore`` — minimises build context.
        """
        project_name: str = env_config.get("project_name", "app")
        db_type: str = env_config.get("db_type", "sqlite")

        try:
            # ── Dockerfile ────────────────────────────────────────────────
            dockerfile = self._build_dockerfile(project_name)
            (project_path / "Dockerfile").write_text(dockerfile)

            # ── docker-compose.yml ─────────────────────────────────────────
            compose = self._build_compose(project_name, db_type)
            (project_path / "docker-compose.yml").write_text(compose)

            # ── .dockerignore ──────────────────────────────────────────────
            dockerignore = (
                "# Python\n"
                "__pycache__/\n"
                "*.py[cod]\n"
                "*.egg-info/\n"
                "dist/\n"
                "build/\n"
                ".venv/\n"
                "venv/\n"
                "env/\n"
                "\n"
                "# Environment\n"
                ".env\n"
                "\n"
                "# IDE\n"
                ".vscode/\n"
                ".idea/\n"
                "*.swp\n"
                ".DS_Store\n"
                "\n"
                "# Database\n"
                "db.sqlite3\n"
                "*.sqlite3\n"
                "\n"
                "# Git\n"
                ".git/\n"
                ".gitignore\n"
                "\n"
                "# uv\n"
                "uv.lock\n"
            )
            (project_path / ".dockerignore").write_text(dockerignore)

        except OSError as exc:
            raise PresetError(f"Failed to write Docker preset files: {exc}") from exc

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _build_dockerfile(project_name: str) -> str:
        python_version = "3.12"
        return (
            f"# ============================================================\n"
            f"# Dockerfile — {project_name}\n"
            f"# Multi-stage build with uv caching\n"
            f"# ============================================================\n"
            f"\n"
            f"# ── Stage 1: Build ──────────────────────────────────────────────\n"
            f"FROM python:{python_version}-slim AS builder\n"
            f"\n"
            f"# Install uv\n"
            f"COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/\n"
            f"\n"
            f"ENV \\\n"
            f"    PYTHONDONTWRITEBYTECODE=1 \\\n"
            f"    PYTHONUNBUFFERED=1 \\\n"
            f"    UV_COMPILE_BYTECODE=1 \\\n"
            f"    UV_LINK_MODE=copy\n"
            f"\n"
            f"WORKDIR /app\n"
            f"\n"
            f"# Install dependencies (layer caching)\n"
            f"RUN --mount=type=cache,target=/root/.cache/uv \\\n"
            f"    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \\\n"
            f"    --mount=type=bind,source=uv.lock,target=uv.lock \\\n"
            f"    uv sync --frozen --no-dev --no-install-project\n"
            f"\n"
            f"# Copy the rest of the application\n"
            f"COPY . .\n"
            f"\n"
            f"# Install the project itself\n"
            f"RUN --mount=type=cache,target=/root/.cache/uv \\\n"
            f"    uv sync --frozen --no-dev\n"
            f"\n"
            f"# ── Stage 2: Runtime ────────────────────────────────────────────\n"
            f"FROM python:{python_version}-slim AS runtime\n"
            f"\n"
            f"# Create non-root user\n"
            f"RUN groupadd -r django && useradd -r -g django django\n"
            f"\n"
            f"WORKDIR /app\n"
            f"\n"
            f"# Copy virtual environment from builder\n"
            f"COPY --from=builder --chown=django:django /app /app\n"
            f"\n"
            f"USER django\n"
            f"\n"
            f"EXPOSE 8000\n"
            f"\n"
            f'CMD ["/app/.venv/bin/python", "manage.py", "runserver", "0.0.0.0:8000"]\n'
        )

    @staticmethod
    def _build_compose(project_name: str, db_type: str) -> str:
        # PostgreSQL service block (only included for postgres/mysql)
        db_service = ""
        db_depends = ""
        db_env = ""

        if db_type == "postgresql":
            db_service = (
                "  db:\n"
                "    image: postgres:16-alpine\n"
                "    restart: unless-stopped\n"
                "    volumes:\n"
                "      - postgres_data:/var/lib/postgresql/data\n"
                "    environment:\n"
                "      POSTGRES_DB: ${DB_NAME:-postgres}\n"
                "      POSTGRES_USER: ${DB_USER:-postgres}\n"
                "      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}\n"
                "    ports:\n"
                '      - "5432:5432"\n'
                "    healthcheck:\n"
                '      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]\n'
                "      interval: 5s\n"
                "      timeout: 3s\n"
                "      retries: 5\n"
                "\n"
            )
            db_depends = "      db:\n        condition: service_healthy\n"
            db_env = "      DB_HOST: db\n"

        return (
            f"# ============================================================\n"
            f"# docker-compose.yml — {project_name}\n"
            f"# ============================================================\n"
            f"\n"
            f"services:\n"
            f"\n"
            f"  # ── Django Web Application ─────────────────────────────────\n"
            f"  web:\n"
            f"    build: .\n"
            f"    restart: unless-stopped\n"
            f"    ports:\n"
            f'      - "8000:8000"\n'
            f"    env_file:\n"
            f"      - .env\n"
            f"    environment:\n"
            f"{db_env}"
            f"    depends_on:\n"
            f"{db_depends}"
            f"      redis:\n"
            f"        condition: service_started\n"
            f"    volumes:\n"
            f"      - .:/app  # Development: mount for live reload\n"
            f"    command: /app/.venv/bin/python manage.py runserver 0.0.0.0:8000\n"
            f"\n"
            f"  # ── Redis (Caching & Sessions) ────────────────────────────\n"
            f"  redis:\n"
            f"    image: redis:7-alpine\n"
            f"    restart: unless-stopped\n"
            f"    ports:\n"
            f'      - "6379:6379"\n'
            f"    volumes:\n"
            f"      - redis_data:/data\n"
            f"\n"
            f"  # ── Mailhog (Email Testing) ───────────────────────────────\n"
            f"  mailhog:\n"
            f"    image: mailhog/mailhog:latest\n"
            f"    restart: unless-stopped\n"
            f"    ports:\n"
            f'      - "8025:8025"  # Web UI\n'
            f'      - "1025:1025"  # SMTP\n'
            f"\n"
            f"{db_service}"
            f"volumes:\n"
            f"  redis_data:\n"
            f"  postgres_data:\n"
        )
