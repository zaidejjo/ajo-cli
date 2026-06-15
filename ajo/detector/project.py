"""Django project detection and state analysis.

The :class:`DjangoProjectDetector` class examines a directory to
determine whether it is a Django project, extracts project metadata
(such as app list, model count, migration status), and makes that
information available for the dashboard UI.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Awaitable

from ajo.detector.cache import DetectorCache


# ── Sentinel for unset values ─────────────────────────────────────────────────

_UNSET: Any = object()

# ── Ruff result type ─────────────────────────────────────────────────────────


class RuffResult:
    """Result of a Ruff lint check.

    Attributes:
        exit_code: ``0`` (clean), ``1`` (issues found), or ``None``
            if ruff was not available.
        line_count: Number of violation lines reported.
        raw_output: Full stdout from the ruff invocation.
    """

    def __init__(
        self, exit_code: int | None, line_count: int = 0, raw_output: str = ""
    ) -> None:
        self.exit_code = exit_code
        self.line_count = line_count
        self.raw_output = raw_output


class DjangoProjectDetector:
    """Detect and analyse a Django project at a given path.

    The constructor performs **only fast, synchronous** checks
    (filesystem reads, environment variables, socket probe).
    Call :meth:`detect_slow` or :meth:`detect_slow_async` to run
    the expensive migration checks, optionally backed by the
    :class:`~ajo.detector.cache.DetectorCache`.

    Usage::

        detector = DjangoProjectDetector(Path("myproject"))
        state = await detector.detect_slow_async()  # cached + threaded
        print(detector.project_info["needs_migrations"])
    """

    # ── Lifecycle ────────────────────────────────────────────────────────

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or Path.cwd()).resolve()
        self.is_django_project = False
        self.project_info: dict[str, Any] = {
            "project_name": "Unknown",
            "settings_module": "Unknown",
            "apps": [],
            "needs_migrations": False,
            "server_running": False,
            "venv_active": False,
            "git_branch": "N/A",
            "models_count": 0,
            "unapplied_migrations": [],
            "has_admin": False,
            "has_static": False,
            "has_media": False,
            "has_superuser": False,  # populated by slow scan; optimistic default
            "ruff_result": None,  # RuffResult | None; populated by slow scan
        }
        self._fast_scan_complete = False
        self._slow_scan_complete = False
        self._cache: DetectorCache | None = None

        # Run fast detection in constructor
        self._detect_fast()

    # ── Fast synchronous detection (constructor) ─────────────────────────

    def _detect_fast(self) -> None:
        """Run only filesystem-fast checks.  Never spawns a subprocess."""
        # Avoid detecting the ajo-cli tool itself
        if self.path.name == "ajo-cli":
            return

        manage_py = self._find_manage_py()
        if not manage_py or not self._verify_django_project(manage_py):
            return

        self.is_django_project = True
        self._extract_project_name(manage_py)
        self.project_info["venv_active"] = self._check_venv()
        self.project_info["server_running"] = self._check_server_running()
        self.project_info["git_branch"] = self._get_git_branch_fast()
        self.project_info["has_static"] = (self.path / "static").exists() or (
            self.path / "staticfiles"
        ).exists()
        self.project_info["has_media"] = (self.path / "media").exists()
        self.project_info["has_admin"] = self._check_admin_enabled()
        self.project_info["apps"] = self._detect_apps()
        self.project_info["models_count"] = self._count_models()
        self._fast_scan_complete = True

    # ── Slow detection (async, cached, threaded) ─────────────────────────

    async def detect_slow_async(
        self,
        *,
        use_cache: bool = True,
        max_workers: int = 2,
    ) -> dict[str, Any]:
        """Run expensive detection checks with caching and thread offloading.

        This method:

        1. Checks the :class:`~ajo.detector.cache.DetectorCache` for a
           fresh entry (if *use_cache* is ``True``).
        2. On cache hit — returns immediately with cached data.
        3. On cache miss — offloads the heavy subprocess calls to a
           background thread pool (limited to *max_workers* concurrent
           threads) and saves the result to cache.

        Args:
            use_cache: Whether to attempt cache lookup first.
            max_workers: Maximum number of simultaneous background
                threads for heavy operations.

        Returns:
            The ``project_info`` dictionary with all fields populated.
        """
        if self._slow_scan_complete:
            return self.project_info

        # ── Cache check ──────────────────────────────────────────────
        if use_cache:
            self._cache = DetectorCache(self.path)
            cached = self._cache.load()
            if cached is not None:
                self.project_info.update(cached)
                self._slow_scan_complete = True
                return self.project_info

        # ── Live fetch with thread offloading ─────────────────────────
        limiter = asyncio.Semaphore(max_workers)

        async def _offload(
            fn: Any,  # callable[[], T]
        ) -> Any:
            async with limiter:
                return await asyncio.to_thread(fn)

        # Launch heavy checks concurrently (limited to max_workers)
        results = await asyncio.gather(
            _offload(self._check_migrations_needed),
            _offload(self._check_unapplied_migrations),
            _offload(self._check_no_superuser),
            _offload(self._check_ruff_status),
            return_exceptions=True,
        )

        mig_needed, unapplied, has_superuser, ruff_result = (
            results[0],
            results[1],
            results[2],
            results[3],
        )

        if not isinstance(mig_needed, Exception):
            self.project_info["needs_migrations"] = mig_needed
        if not isinstance(unapplied, Exception):
            self.project_info["unapplied_migrations"] = unapplied
        if not isinstance(has_superuser, Exception):
            self.project_info["has_superuser"] = has_superuser
        if not isinstance(ruff_result, Exception):
            self.project_info["ruff_result"] = ruff_result

        # ── Persist to cache ─────────────────────────────────────────
        if use_cache and self._cache is not None:
            self._cache.save(self.project_info)

        self._slow_scan_complete = True
        return self.project_info

    # ── Public helpers ───────────────────────────────────────────────────

    @property
    def cache(self) -> DetectorCache | None:
        """Return the :class:`DetectorCache` instance, if initialised."""
        return self._cache

    # ── Filesystem helpers (all sync, zero subprocess) ───────────────────

    def _find_manage_py(self) -> Path | None:
        manage_py = self.path / "manage.py"
        if manage_py.exists():
            return manage_py
        for parent in self.path.parents:
            if (parent / "manage.py").exists():
                self.path = parent
                return parent / "manage.py"
        return None

    @staticmethod
    def _verify_django_project(manage_py: Path) -> bool:
        try:
            content = manage_py.read_text(encoding="utf-8", errors="ignore")
            return "django.core.management" in content
        except Exception:
            return False

    def _extract_project_name(self, manage_py: Path) -> None:
        try:
            content = manage_py.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"DJANGO_SETTINGS_MODULE\s*=\s*['\"]([^'\"]+)", content)
            if match:
                self.project_info["settings_module"] = match.group(1)
                self.project_info["project_name"] = match.group(1).split(".")[0]
            else:
                self.project_info["project_name"] = self.path.name
        except Exception:
            self.project_info["project_name"] = self.path.name

    def _detect_apps(self) -> list[dict[str, Any]]:
        apps: list[dict[str, Any]] = []
        try:
            for item in self.path.iterdir():
                if (
                    not item.is_dir()
                    or item.name.startswith(".")
                    or item.name == "config"
                ):
                    continue
                is_app = (item / "apps.py").exists() or (item / "models.py").exists()
                if not is_app:
                    continue
                apps.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "has_models": (item / "models.py").exists(),
                        "has_admin": (item / "admin.py").exists(),
                        "has_views": (item / "views.py").exists(),
                        "has_urls": (item / "urls.py").exists(),
                        "has_templates": (item / "templates").exists(),
                        "has_migrations": (item / "migrations").exists(),
                        "is_installed": self._is_in_installed_apps(item.name),
                        "models_count": self._count_app_models(item),
                    }
                )
        except Exception:
            pass
        return apps

    def _count_app_models(self, app_path: Path) -> int:
        try:
            models_file = app_path / "models.py"
            if models_file.exists():
                content = models_file.read_text(encoding="utf-8", errors="ignore")
                return len(re.findall(r"class\s+(\w+)\s*\(.*models\.Model\)", content))
        except Exception:
            pass
        return 0

    def _is_in_installed_apps(self, app_name: str) -> bool:
        try:
            settings_dir = (
                self.path / str(self.project_info.get("project_name", "")) / "settings"
            )
            files_to_check: list[Path] = (
                list(settings_dir.glob("*.py")) if settings_dir.exists() else []
            )
            single_settings = self._find_settings_path()
            if single_settings:
                files_to_check.append(single_settings)
            for settings_file in files_to_check:
                content = settings_file.read_text(encoding="utf-8", errors="ignore")
                if (
                    f"'{app_name}'" in content
                    or f'"{app_name}"' in content
                    or f"{app_name}.apps" in content
                ):
                    return True
        except Exception:
            pass
        return False

    def _find_settings_path(self) -> Path | None:
        p_name = str(self.project_info.get("project_name", ""))
        paths = [
            self.path / p_name / "settings.py",
            self.path / "settings.py",
        ]
        for p in paths:
            if p.exists():
                return p
        for p in self.path.glob("**/settings.py"):
            return p
        return None

    # ── Fast synchronous checks (no subprocess) ──────────────────────────

    @staticmethod
    def _check_venv() -> bool:
        return bool(os.environ.get("VIRTUAL_ENV")) or bool(
            os.environ.get("UV_PROJECT_ENVIRONMENT")
        )

    def _check_server_running(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.2)
                return sock.connect_ex(("127.0.0.1", 8000)) == 0
        except Exception:
            return False

    def _check_admin_enabled(self) -> bool:
        try:
            p_name = str(self.project_info.get("project_name", ""))
            urls_path = self.path / p_name / "urls.py"
            if not urls_path.exists():
                urls_path = self.path / "urls.py"
            if urls_path.exists():
                return "admin.site.urls" in urls_path.read_text(
                    encoding="utf-8", errors="ignore"
                )
        except Exception:
            pass
        return False

    def _count_models(self) -> int:
        return sum(
            app.get("models_count", 0) for app in self.project_info.get("apps", [])
        )

    # ── Subprocess-based helpers (heavy, designed for thread offload) ────

    def _get_git_branch_fast(self) -> str:
        """Read git branch from ``.git/HEAD`` — zero subprocesses."""
        head_file = self.path / ".git" / "HEAD"
        if not head_file.exists():
            return "N/A"
        try:
            content = head_file.read_text(encoding="utf-8", errors="replace").strip()
            if content.startswith("ref: "):
                return content.removeprefix("ref: refs/heads/")
            return content[:7]
        except Exception:
            return "N/A"

    def _check_migrations_needed(self) -> bool:
        """Heavy: spawn ``uv run manage.py makemigrations --dry-run``."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "manage.py", "makemigrations", "--dry-run"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "No changes detected" not in result.stdout and result.returncode == 0
        except Exception:
            return False

    def _check_unapplied_migrations(self) -> list[str]:
        """Heavy: spawn ``uv run manage.py showmigrations --plan``."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "manage.py", "showmigrations", "--plan"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                unapplied: list[str] = []
                for line in result.stdout.splitlines():
                    if "[ ]" in line:
                        clean = line.replace("[ ]", "").strip()
                        if clean:
                            unapplied.append(clean)
                return unapplied
        except Exception:
            pass
        return []

    def _check_no_superuser(self) -> bool:
        """Check whether at least one superuser exists.

        Returns ``True`` if a superuser was found, ``False`` if none
        exist or if the check fails for any reason (no database, no
        Django, etc.).

        **Heavy**: spawns a ``django-admin`` shell command inside the
        project's ``uv`` environment.
        """
        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "manage.py",
                    "shell",
                    "-c",
                    (
                        "from django.contrib.auth.models import User;"
                        "print(User.objects.filter(is_superuser=True).exists())"
                    ),
                ],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() == "True"
        except Exception:
            return False

    def _check_ruff_status(self) -> RuffResult | None:
        """Run Ruff lint check on the project.

        Only runs if ``ruff`` is on the ``PATH`` (checked via
        :func:`shutil.which`).  Returns a :class:`RuffResult` or
        ``None`` if Ruff is not installed.

        **Heavy**: spawns ``ruff check`` across the whole project tree
        (though Ruff is typically very fast).
        """
        if not shutil.which("ruff"):
            return None
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format", "concise", "--quiet", "."],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=15,
            )
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            return RuffResult(
                exit_code=result.returncode,
                line_count=len(lines),
                raw_output=result.stdout,
            )
        except Exception:
            return None
