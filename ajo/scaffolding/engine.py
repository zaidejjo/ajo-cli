"""Transactional scaffold engine with atomic step execution and rollback.

The :class:`ScaffoldEngine` orchestrates the project bootstrapping
pipeline — directory creation, ``git`` initialisation, dependency
installation, preset-specific scaffolding — and wraps every step with
:class:`RollbackManager` so that any failure (exception or
:exc:`KeyboardInterrupt`) triggers a clean, LIFO-ordered teardown.

Progress integration
--------------------
High-latency steps (``uv add``, ``uv sync``) use
:class:`~ajo.ui.progress.AsyncProgressManager` to render live,
non-blocking progress bars with streaming subprocess output.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import signal
from pathlib import Path
from types import FrameType
from typing import Any, Callable

from ajo.core.exceptions import PresetError, RollbackError
from ajo.plugins.hooks import PluginManager
from ajo.presets.addons import AbstractAddon
from ajo.ui.progress import AsyncProgressManager, run_command_streaming

logger = logging.getLogger(__name__)


# =============================================================================
# ROLLBACK MANAGER
# =============================================================================


class RollbackManager:
    """A journal stack of undo actions for atomic operation groups.

    Usage::

        rb = RollbackManager()
        rb.push("create directory", lambda: shutil.rmtree(path))
        rb.push("write file", lambda: path.unlink(missing_ok=True))
        # ... if something fails later:
        rb.execute_all()  # runs in LIFO order; best-effort
    """

    def __init__(self) -> None:
        self._stack: list[tuple[str, Callable[[], None]]] = []

    # ── Public API ───────────────────────────────────────────────────────

    def push(self, description: str, action: Callable[[], None]) -> None:
        """Register a rollback action.

        Args:
            description: Human-readable label for logging / error messages.
            action: Zero-argument callable that undoes the corresponding
                forward step.
        """
        self._stack.append((description, action))

    def execute_all(self) -> None:
        """Execute every registered rollback action in LIFO order.

        Each action is attempted even if a previous one fails; error
        messages are collected and raised as a single
        :exc:`~ajo.core.exceptions.RollbackError` at the end.  If
        all actions succeed the function returns silently.
        """
        errors: list[str] = []
        for description, action in reversed(self._stack):
            try:
                action()
                logger.debug("Rollback OK: %s", description)
            except Exception as exc:
                msg = f"{description}: {exc}"
                logger.warning("Rollback failure: %s", msg)
                errors.append(msg)
        self._stack.clear()

        if errors:
            raise RollbackError("Rollback completed with errors:\n" + "\n".join(errors))

    @property
    def has_actions(self) -> bool:
        """``True`` if at least one action is registered."""
        return len(self._stack) > 0

    def __len__(self) -> int:
        return len(self._stack)


# =============================================================================
# SCAFFOLD ENGINE
# =============================================================================


class ScaffoldEngine:
    """Orchestrates the project-scaffolding pipeline atomically.

    Each logical step (create directory, init git, install deps, etc.)
    is wrapped with a corresponding rollback action.  If any step raises
    an exception, or if the user presses :kbd:`Ctrl+C`, all completed
    steps are undone in reverse order, leaving the filesystem clean.

    Usage::

        engine = ScaffoldEngine(project_path, env_config={...})
        success = await engine.execute(preset=my_preset)
    """

    def __init__(
        self,
        project_path: Path,
        *,
        env_config: dict[str, Any] | None = None,
        plugin_manager: PluginManager | None = None,
    ) -> None:
        self.project_path = project_path.resolve()
        self.env_config = env_config or {}
        self._rollback = RollbackManager()
        self._interrupted = False
        self._preset: Any | None = None
        self._addons: list[AbstractAddon] | None = None
        self._plugin_manager: PluginManager | None = plugin_manager

        # Populate defaults if not provided
        self.env_config.setdefault("project_name", project_path.name)
        self.env_config.setdefault("db_type", "sqlite")
        self.env_config.setdefault("db_config", {})

    # ── Public API ───────────────────────────────────────────────────────

    async def execute(
        self,
        preset: Any | None = None,
        addons: list[AbstractAddon] | None = None,
        *,
        dry_run: bool = False,
    ) -> bool:
        """Run the full scaffold pipeline atomically.

        Steps (in order):

        1. Create the project directory.
        2. Create ``.env`` with a generated ``SECRET_KEY``.
        3. Create ``.gitignore``.
        4. Initialise ``git``.
        5. Initialise ``uv`` (``uv init --bare``).
        6. Install project dependencies from preset or defaults.
        7. Install dev-dependencies from preset.
        8. Run the **preset**'s ``scaffold()`` coroutine.
        9. Install add-on dependencies (aggregated across all add-ons).
        10. Install add-on dev-dependencies (aggregated).
        11. Run each **add-on**'s ``apply()`` coroutine.
        12. Run ``uv sync`` to lock the environment.

        If any step fails, all completed steps are rolled back.

        When *dry_run* is ``True``, no filesystem changes are made; each step
        is logged at INFO level and the method returns ``True`` immediately.

        Args:
            preset: An optional :class:`~ajo.presets.base.AbstractPreset`
                instance whose ``scaffold()``, ``dependencies``, and
                ``dev_dependencies`` will be used.
            addons: An optional list of :class:`~ajo.presets.addons.AbstractAddon`
                instances to layer on top of the preset.
            dry_run: If ``True``, log planned steps but do not execute them.

        Returns:
            ``True`` if the scaffold completed successfully, ``False``
            if it was interrupted or rolled back.
        """
        # Each step is a (description, callable) pair.  The callable may
        # be sync or async (coroutine function); the execution loop
        # adapts.
        steps: list[tuple[str, Callable[..., Any]]] = [
            ("Creating project directory", self._step_create_directory),
            ("Creating .env file", self._step_create_env),
            ("Creating .gitignore", self._step_create_gitignore),
        ]

        if preset is not None:
            deps = getattr(preset, "dependencies", [])
            if deps:
                steps.append(
                    ("Installing dependencies", lambda: self._step_uv_add(deps))
                )
            dev_deps = getattr(preset, "dev_dependencies", [])
            if dev_deps:
                steps.append(
                    (
                        "Installing dev dependencies",
                        lambda: self._step_uv_add_dev(dev_deps),
                    )
                )

        steps.extend(
            [
                ("Initialising git repository", self._step_git_init),
                ("Initialising uv project", self._step_uv_init),
            ]
        )

        if preset is not None:
            self._preset = preset  # store for preview
            scaffold_fn = getattr(preset, "scaffold", None)
            if scaffold_fn is not None:
                steps.append(
                    (
                        f"Running {preset.name} preset",
                        lambda: self._step_preset(preset),
                    )
                )

        if self._plugin_manager is not None:
            steps.append(
                (
                    "Running pre-scaffold hooks",
                    self._step_pre_hooks,
                )
            )

        if addons:
            self._addons = addons  # store for preview / rollback
            addon_deps: list[str] = []
            addon_dev_deps: list[str] = []
            for addon in addons:
                addon_deps.extend(getattr(addon, "dependencies", []))
                addon_dev_deps.extend(getattr(addon, "dev_dependencies", []))

            if addon_deps:
                steps.append(
                    (
                        "Installing add-on dependencies",
                        lambda deps=addon_deps: self._step_uv_add(deps),
                    )
                )
            if addon_dev_deps:
                steps.append(
                    (
                        "Installing add-on dev dependencies",
                        lambda deps=addon_dev_deps: self._step_uv_add_dev(deps),
                    )
                )

            steps.append(
                (
                    "Applying add-on modules",
                    lambda: self._step_addon(addons),
                )
            )

        if self._plugin_manager is not None:
            steps.append(
                (
                    "Running post-scaffold hooks",
                    self._step_post_hooks,
                )
            )

        steps.append(("Running uv sync", self._step_uv_sync))

        # ── Dry-run: log steps and return without making changes ──────
        if dry_run:
            for description, _ in steps:
                logger.info("[DRY RUN] %s", description)
            return True

        # ── Install SIGINT handler ───────────────────────────────────
        original_handler: Any = None
        try:
            original_handler = signal.signal(
                signal.SIGINT,
                self._signal_handler,
            )
        except (ValueError, RuntimeError):
            pass  # Not in main thread — accept default behaviour

        # ── Execute steps ────────────────────────────────────────────
        try:
            for description, step_fn in steps:
                if self._interrupted:
                    logger.warning("Scaffold interrupted by user")
                    break
                logger.info("Step: %s", description)
                try:
                    result = step_fn()
                    if asyncio.iscoroutine(result):
                        await result
                except (PresetError, OSError) as exc:
                    logger.error("Step failed: %s — %s", description, exc)
                    self._rollback.execute_all()
                    return False
                except Exception as exc:
                    logger.error("Step failed (unexpected): %s — %s", description, exc)
                    self._rollback.execute_all()
                    return False

            if self._interrupted:
                self._rollback.execute_all()
                return False

            return True

        except KeyboardInterrupt:
            self._interrupted = True
            self._rollback.execute_all()
            return False

        finally:
            # Restore original signal handler
            if original_handler is not None:
                try:
                    signal.signal(signal.SIGINT, original_handler)
                except (ValueError, RuntimeError):
                    pass

    # ── Internal signal handler ──────────────────────────────────────────

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:  # noqa: ARG002
        """Mark the engine as interrupted; the step loop picks this up."""
        self._interrupted = True
        logger.info("Received SIGINT — interrupting scaffold after current step")

    # ── Individual step implementations ──────────────────────────────────

    def _step_create_directory(self) -> None:
        """Create the project root directory."""
        self.project_path.mkdir(parents=True, exist_ok=False)
        self._rollback.push(
            f"remove directory {self.project_path}",
            lambda: shutil.rmtree(self.project_path, ignore_errors=True),
        )

    def _step_create_env(self) -> None:
        """Generate a ``.env`` file with a secure secret key."""
        from ajo.utils import generate_secure_key

        env_path = self.project_path / ".env"
        db_type: str = self.env_config.get("db_type", "sqlite")
        db_config: dict[str, Any] = self.env_config.get("db_config", {})
        secret_key = generate_secure_key()

        lines = [
            "# ============================================================",
            "# DJANGO SECURITY",
            "# ============================================================",
            f"SECRET_KEY={secret_key}",
            "DEBUG=True",
            "ALLOWED_HOSTS=127.0.0.1,localhost",
            "",
            "# ============================================================",
            "# DATABASE CONFIGURATION",
            "# ============================================================",
            f"DB_TYPE={db_type}",
        ]

        if db_type == "postgresql":
            lines.extend(
                [
                    f"DB_NAME={db_config.get('name', 'postgres')}",
                    f"DB_USER={db_config.get('user', 'postgres')}",
                    f"DB_PASSWORD={db_config.get('password', '')}",
                    f"DB_HOST={db_config.get('host', 'localhost')}",
                    f"DB_PORT={db_config.get('port', '5432')}",
                ]
            )
        elif db_type == "mysql":
            lines.extend(
                [
                    f"DB_NAME={db_config.get('name', 'mysql')}",
                    f"DB_USER={db_config.get('user', 'root')}",
                    f"DB_PASSWORD={db_config.get('password', '')}",
                    f"DB_HOST={db_config.get('host', 'localhost')}",
                    f"DB_PORT={db_config.get('port', '3306')}",
                ]
            )

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._rollback.push(
            f"remove .env",
            lambda: self._safe_unlink(env_path),
        )

    def _step_create_gitignore(self) -> None:
        """Generate a ``.gitignore``."""
        gitignore_path = self.project_path / ".gitignore"
        content = (
            "# Environment\n.env\n.venv\nvenv/\nenv/\n\n"
            "# Python\n__pycache__/\n*.py[cod]\n*.so\n.Python\n"
            "*.egg-info/\ndist/\nbuild/\n\n"
            "# Database\ndb.sqlite3\n*.sqlite3\n\n"
            "# Django\n*.log\nlocal_settings.py\n/static/\n/media/\nstaticfiles/\n\n"
            "# uv\nuv.lock\n\n"
            "# IDE\n.vscode/\n.idea/\n*.swp\n.DS_Store\n"
        )
        gitignore_path.write_text(content, encoding="utf-8")
        self._rollback.push(
            "remove .gitignore",
            lambda: self._safe_unlink(gitignore_path),
        )

    async def _step_uv_init(self) -> None:
        """Initialise ``uv`` in the project directory."""
        from ajo.gateway.uv import uv_init

        try:
            await uv_init(self.project_path)
        except Exception as exc:
            raise PresetError(f"uv init failed: {exc}") from exc

        # Register rollback: remove uv-managed files
        def _undo_uv_init() -> None:
            for fname in ("pyproject.toml", "uv.lock"):
                p = self.project_path / fname
                self._safe_unlink(p)

        self._rollback.push("undo uv init", _undo_uv_init)

    async def _step_uv_add(self, packages: list[str]) -> None:
        """Install runtime dependencies with live progress."""
        from ajo.core.exceptions import CommandExecutionError

        if not packages:
            return
        try:
            async with AsyncProgressManager() as _pm:
                _task_id = _pm.add_task(
                    f"Installing {' '.join(packages)}",
                    total=100,
                )
                _returncode, _output = await run_command_streaming(
                    ["uv", "add", *packages],
                    task_id=_task_id,
                    progress_manager=_pm,
                    description_prefix="uv add",
                )
                if _returncode != 0:
                    raise PresetError(
                        f"uv add {' '.join(packages)} failed (exit {_returncode})"
                    )
        except CommandExecutionError as exc:
            raise PresetError(f"uv add {' '.join(packages)} failed: {exc}") from exc

    async def _step_uv_add_dev(self, packages: list[str]) -> None:
        """Install dev dependencies with live progress."""
        from ajo.core.exceptions import CommandExecutionError

        if not packages:
            return
        try:
            async with AsyncProgressManager() as _pm:
                _task_id = _pm.add_task(
                    f"Installing dev {' '.join(packages)}",
                    total=100,
                )
                _returncode, _output = await run_command_streaming(
                    ["uv", "add", "--dev", *packages],
                    task_id=_task_id,
                    progress_manager=_pm,
                    description_prefix="uv add --dev",
                )
                if _returncode != 0:
                    raise PresetError(
                        f"uv add --dev {' '.join(packages)} failed (exit {_returncode})"
                    )
        except CommandExecutionError as exc:
            raise PresetError(
                f"uv add --dev {' '.join(packages)} failed: {exc}"
            ) from exc

    async def _step_git_init(self) -> None:
        """Initialise a Git repository."""
        from ajo.gateway.git import git_init

        try:
            await git_init(self.project_path)
        except Exception as exc:
            raise PresetError(f"git init failed: {exc}") from exc

        self._rollback.push(
            "remove .git directory",
            lambda: shutil.rmtree(self.project_path / ".git", ignore_errors=True),
        )

    async def _step_preset(self, preset: Any) -> None:
        """Run the preset's ``scaffold()`` coroutine."""
        try:
            await preset.scaffold(self.project_path, self.env_config)
        except PresetError:
            raise
        except Exception as exc:
            raise PresetError(f"{preset.name} preset scaffold failed: {exc}") from exc

        # Register a coarse rollback that deletes every file the preset
        # may have created (except .env and .gitignore).
        def _undo_preset() -> None:
            for child in self.project_path.iterdir():
                if child.name in (
                    ".env",
                    ".gitignore",
                    ".git",
                    "pyproject.toml",
                    "uv.lock",
                ):
                    continue
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    self._safe_unlink(child)

        self._rollback.push(f"undo {preset.name} preset", _undo_preset)

    async def _step_addon(self, addons: list[AbstractAddon]) -> None:
        """Run each add-on's ``apply()`` coroutine."""
        project_name: str = self.env_config.get("project_name", self.project_path.name)

        for addon in addons:
            try:
                await addon.apply(self.project_path, project_name, self.env_config)
            except PresetError:
                raise
            except Exception as exc:
                raise PresetError(f"Add-on '{addon.name}' apply failed: {exc}") from exc

        # Register a coarse rollback that deletes every file the add-ons
        # may have created (except known infrastructure files).
        def _undo_addon() -> None:
            for child in self.project_path.iterdir():
                if child.name in (
                    ".env",
                    ".gitignore",
                    ".git",
                    "pyproject.toml",
                    "uv.lock",
                ):
                    continue
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    self._safe_unlink(child)

        self._rollback.push("undo add-on modules", _undo_addon)

    # ── Plugin hook steps ────────────────────────────────────────────────

    async def _step_pre_hooks(self) -> None:
        """Execute all loaded ``pre_scaffold`` plugin hooks."""
        if self._plugin_manager is None:
            return
        errors = await self._plugin_manager.execute_pre_scaffold(
            self.project_path,
            self.env_config,
        )
        if errors:
            raise PresetError(
                f"Pre-scaffold hook(s) failed: {'; '.join(str(e) for e in errors)}"
            )

    async def _step_post_hooks(self) -> None:
        """Execute all loaded ``post_scaffold`` plugin hooks."""
        if self._plugin_manager is None:
            return
        errors = await self._plugin_manager.execute_post_scaffold(
            self.project_path,
            self.env_config,
        )
        if errors:
            raise PresetError(
                f"Post-scaffold hook(s) failed: {'; '.join(str(e) for e in errors)}"
            )

    async def _step_uv_sync(self) -> None:
        """Run ``uv sync`` to lock the environment with live progress."""
        from ajo.core.exceptions import CommandExecutionError

        try:
            async with AsyncProgressManager() as _pm:
                _task_id = _pm.add_task(
                    "Locking environment (uv sync)",
                    total=100,
                )
                _returncode, _output = await run_command_streaming(
                    ["uv", "sync"],
                    task_id=_task_id,
                    progress_manager=_pm,
                    description_prefix="uv sync",
                )
                if _returncode != 0:
                    raise PresetError(f"uv sync failed (exit {_returncode})")
        except CommandExecutionError as exc:
            raise PresetError(f"uv sync failed: {exc}") from exc

    # ── Preview support ──────────────────────────────────────────────────

    def get_preview_files(self) -> list[tuple[str, int]]:
        """Return a list of ``(relative_path, byte_size)`` for files and
        directories that will be created by the scaffold.

        This is used by :class:`~ajo.ui.theme.FileTreePreview` to render
        a live preview before the user confirms scaffolding.

        Returns:
            List of ``(path, size)`` tuples.  Directories have size ``0``.
        """
        files: list[tuple[str, int]] = []
        project_name = self.env_config.get("project_name", self.project_path.name)

        # Core files always created
        core_files: list[tuple[str, int]] = [
            (f"{project_name}/", 0),
            (f"{project_name}/.env", 512),
            (f"{project_name}/.gitignore", 256),
            (f"{project_name}/pyproject.toml", 1024),
        ]

        # Preset-specific files — we look at what the preset might generate
        preset = getattr(self, "_preset", None)
        if preset is not None:
            preset_files = getattr(preset, "preview_files", None)
            if preset_files is not None:
                core_files.extend(
                    (f"{project_name}/{path}", size) for path, size in preset_files
                )

        # Add-on-specific preview files
        addons = getattr(self, "_addons", None)
        if addons is not None:
            for addon in addons:
                addon_files = getattr(addon, "preview_files", None)
                if addon_files is not None:
                    core_files.extend(
                        (f"{project_name}/{path}", size) for path, size in addon_files
                    )

        # De-duplicate (keep first occurrence)
        seen: set[str] = set()
        for path, size in core_files:
            if path not in seen:
                seen.add(path)
                files.append((path, size))

        return files

    # ── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        """Remove a file, ignoring ``FileNotFoundError``."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
