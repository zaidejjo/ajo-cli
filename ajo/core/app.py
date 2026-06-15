"""Application lifecycle and async entry point support.

Provides the :func:`async_entry` decorator that wraps an ``async def``
main coroutine and runs it with :func:`asyncio.run`, giving the whole
application access to the async gateway layer.
"""

from __future__ import annotations

import asyncio
import functools
import signal
from collections.abc import Callable, Coroutine
from typing import TypeVar

from ajo.core.exceptions import CommandExecutionError

# Type variable for the return type of the wrapped function.
R = TypeVar("R")


def async_entry(
    func: Callable[..., Coroutine[None, None, R]],
) -> Callable[..., R]:
    """Decorate an ``async def`` entry point so it can be called synchronously.

    The decorator uses :func:`asyncio.run` to bootstrap the event loop,
    configures graceful handling of :data:`signal.SIGINT` (Ctrl+C), and
    ensures subprocesses are cleaned up even on cancellation.

    Usage::

        @async_entry
        async def main() -> int:
            await uv_init(Path("myproject"))
            return 0

        if __name__ == "__main__":
            sys.exit(main())
    """

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> R:
        # Register a simple handler so KeyboardInterrupt surfaces
        # cleanly through asyncio.run().
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        main_task: asyncio.Task | None = None

        def _signal_handler() -> None:
            if main_task is not None and not main_task.done():
                main_task.cancel()

        try:
            # Attempt to set up SIGINT handling if we are on a POSIX
            # platform (asyncio.run does this automatically in 3.12+).
            try:
                loop.add_signal_handler(signal.SIGINT, _signal_handler)
            except (NotImplementedError, ValueError):
                pass  # Windows or not in main thread — accept default behaviour

            main_task = loop.create_task(func(*args, **kwargs))
            return loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            return 130  # type: ignore[return-value]
        finally:
            try:
                # Give subprocesses a moment to clean up.
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except (asyncio.CancelledError, RuntimeError):
                pass
            finally:
                loop.close()

    return wrapper


def format_command_error(exc: CommandExecutionError) -> str:
    """Format a :exc:`CommandExecutionError` into a human-readable message.

    Args:
        exc: The exception to format.

    Returns:
        A multi-line string suitable for rendering in a Rich panel or
        console output.
    """
    lines: list[str] = []
    command_str = " ".join(exc.command) if exc.command else "<unknown>"
    lines.append(f"  Command:  {command_str}")
    if exc.return_code is not None:
        lines.append(f"  Exit code: {exc.return_code}")
    if exc.stderr:
        lines.append(f"  stderr:   {exc.stderr}")
    return "\n".join(lines)
