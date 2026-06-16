"""Lazy import tracker and performance monitor for startup-time optimisation.

Monitors import times at runtime and emits warnings for any module that
exceeds the configurable threshold (default 5ms).  All heavy UI imports
(Rich, InquirerPy) should go through this tracker so that startup times
remain under 50ms.
"""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any

logger = logging.getLogger("ajo.performance")


class LazyImportTracker:
    """Track import times and warn about slow modules.

    Usage::

        InquirerPy = LazyImportTracker.import_module("InquirerPy")
        Console = LazyImportTracker.import_module("rich.console").Console
    """

    _imports: dict[str, float] = {}
    _cache: dict[str, Any] = {}
    _THRESHOLD_MS: float = 5.0

    @classmethod
    def import_module(cls, module_path: str) -> Any:
        """Import a module by dotted path, measuring and caching the result.

        Args:
            module_path: Dotted module path (e.g. ``"rich.console"``).

        Returns:
            The imported module object.

        Note:
            If the import takes longer than ``_THRESHOLD_MS`` (default 5ms),
            a warning is logged.  The result is cached so repeated calls
            are free.
        """
        if module_path in cls._cache:
            return cls._cache[module_path]

        start = time.perf_counter()
        module = importlib.import_module(module_path)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        cls._imports[module_path] = elapsed
        cls._cache[module_path] = module

        if elapsed > cls._THRESHOLD_MS:
            logger.warning(
                "Slow import: %s took %.1fms (threshold: %.1fms)",
                module_path,
                elapsed,
                cls._THRESHOLD_MS,
            )

        return module

    @classmethod
    def get_import_report(cls) -> dict[str, float]:
        """Return a dict of ``{module_path: elapsed_ms}`` for all imports.

        Useful for debugging and profiling.
        """
        return dict(cls._imports)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the module cache (useful for testing)."""
        cls._cache.clear()
        cls._imports.clear()


# ── Convenience helper for lazy attribute access on modules ──────────────


def lazy_attr(module_path: str, attr_name: str) -> Any:
    """Lazily import *module_path* and return *attr_name* from it.

    This is a one-liner for the common ``from X import Y`` pattern::

        Console = lazy_attr("rich.console", "Console")
        # Equivalent to: from rich.console import Console

    Args:
        module_path: Dotted module path.
        attr_name: Attribute (class, function, etc.) to extract.

    Returns:
        The requested attribute from the imported module.
    """
    module = LazyImportTracker.import_module(module_path)
    return getattr(module, attr_name)
