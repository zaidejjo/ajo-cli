"""Asynchronous progress manager with streaming output.

Provides the :class:`AsyncProgressManager` that wraps Rich's Progress
bars in an async context manager, and the :func:`_run_command_streaming`
adapter that feeds subprocess stdout/stderr into a progress callback.

Usage::

    async with AsyncProgressManager() as pm:
        task_id = pm.add_task("Running migrations...", total=100)
        await some_work(pm.update)
        pm.update(task_id, completed=100)
"""

from __future__ import annotations

import asyncio
import contextlib
import subprocess  # noqa: S404
import sys
from typing import Any, AsyncIterator, Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ajo.core.color_control import configure_console, should_disable_progress
from ajo.ui.theme import ThemeEngine


# ── Progress callback type ───────────────────────────────────────────────

ProgressCallback = Callable[[int, str | None], None]
"""Signature: ``(completed: int, description: str | None) -> None``."""


# ── AsyncProgressManager ─────────────────────────────────────────────────


class AsyncProgressManager:
    """Async context manager for Rich progress bars.

    Features
    --------
    - Non-blocking progress display via asyncio.
    - Multiple simultaneous tasks.
    - Dynamic description updates.
    - Auto-cleanup on exit.

    Usage::

        async with AsyncProgressManager() as pm:
            t1 = pm.add_task("Task 1", total=100)
            t2 = pm.add_task("Task 2", total=50)

            for i in range(100):
                pm.update(t1, advance=1)
                if i % 2 == 0:
                    pm.update(t2, advance=1)
                await asyncio.sleep(0.05)
    """

    def __init__(
        self,
        console: Console | None = None,
        engine: ThemeEngine | None = None,
        *,
        disable: bool | None = None,
    ) -> None:
        self._engine = engine or ThemeEngine.get_instance()
        self._disable = disable if disable is not None else should_disable_progress()
        self._console = console or configure_console()
        self._progress: Progress | None = None
        self._refresh_task: asyncio.Task[None] | None = None

    @property
    def progress(self) -> Progress:
        """Return the underlying :class:`rich.progress.Progress` instance."""
        assert self._progress is not None, "Not in context"
        return self._progress

    # ── Context manager ───────────────────────────────────────────────

    async def __aenter__(self) -> AsyncProgressManager:
        theme = self._engine.palette

        self._progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(
                complete_style=theme.primary,
                finished_style=theme.success,
                pulse_style=theme.muted,
            ),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            expand=True,
            disable=self._disable,
        )

        self._progress.start()
        # Start a background refresh loop for live updates
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._progress:
            self._progress.stop()
            self._progress = None

    async def _refresh_loop(self) -> None:
        """Periodically refresh the Rich live display."""
        try:
            while True:
                await asyncio.sleep(0.05)
                if self._progress:
                    self._progress.refresh()
        except asyncio.CancelledError:
            pass

    # ── Task management ───────────────────────────────────────────────

    def add_task(
        self,
        description: str,
        *,
        total: int | None = None,
        completed: int = 0,
        visible: bool = True,
    ) -> int:
        """Add a new progress task.

        Args:
            description: Task label.
            total: Total steps (``None`` for indeterminate).
            completed: Initial completed count.
            visible: Whether the task is visible.

        Returns:
            Task ID (int) for subsequent ``update()`` calls.
        """
        return self.progress.add_task(
            description,
            total=total,
            completed=completed,
            visible=visible,
        )

    def update(
        self,
        task_id: int,
        *,
        completed: int | None = None,
        advance: int | None = None,
        description: str | None = None,
        total: int | None = None,
        visible: bool | None = None,
    ) -> None:
        """Update a progress task's state.

        Args:
            task_id: The task ID to update.
            completed: Set absolute completed value.
            advance: Increment completed by this amount.
            description: New description text.
            total: Update total steps.
            visible: Show/hide the task.
        """
        kwargs: dict[str, Any] = {}
        if completed is not None:
            kwargs["completed"] = completed
        if advance is not None:
            kwargs["advance"] = advance
        if description is not None:
            kwargs["description"] = description
        if total is not None:
            kwargs["total"] = total
        if visible is not None:
            kwargs["visible"] = visible

        self.progress.update(task_id, **kwargs)

    def remove_task(self, task_id: int) -> None:
        """Remove a task from the progress display."""
        self.progress.remove_task(task_id)


# ── Command-streaming helper ─────────────────────────────────────────────


async def run_command_streaming(
    cmd: list[str],
    *,
    task_id: int,
    progress_manager: AsyncProgressManager,
    total_steps: int = 100,
    description_prefix: str = "Running",
    capture_output: bool = True,
) -> tuple[int, str]:
    """Run a subprocess while streaming output to a progress bar.

    This is an async wrapper around :func:`_run_command_streaming`
    that ties into the :class:`AsyncProgressManager`.

    Args:
        cmd: Command and arguments (e.g. ``["python", "manage.py", "migrate"]``).
        task_id: Progress task ID to update.
        progress_manager: Active progress manager instance.
        total_steps: Total steps for progress completion.
        description_prefix: Text shown before the command name.
        capture_output: If ``True``, return combined stdout+stderr.

    Returns:
        ``(return_code, output_text)``.

    Note:
        The subprocess is run in a thread to avoid blocking the event loop.
    """
    progress_manager.update(
        task_id,
        description=f"{description_prefix}: {' '.join(cmd)}",
        total=total_steps,
    )

    def _run() -> tuple[int, str]:
        import subprocess  # noqa: S404

        output_parts: list[str] = []
        step = 0

        with subprocess.Popen(  # noqa: S602
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if capture_output else subprocess.DEVNULL,
            text=True,
            bufsize=1,
        ) as proc:
            assert proc.stdout is not None
            for line in proc.stdout:
                output_parts.append(line)
                step = min(step + 1, total_steps - 1)
                progress_manager.update(
                    task_id,
                    advance=1,
                    description=f"{description_prefix}: {line.rstrip()[:60]}",
                )
            proc.wait()
            # Mark complete
            progress_manager.update(task_id, completed=total_steps)
            return proc.returncode or 0, "".join(output_parts)

    return await asyncio.to_thread(_run)
