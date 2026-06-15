"""Filesystem-backed state cache for Django project detection.

The :class:`DetectorCache` serialises the project's detected state
(such as app list, model count, migration status) to a JSON file at
``.ajo_cache/detector_state.json`` inside the project root.  This
avoids re-running expensive ``manage.py`` commands on every invocation
of ``ajo``.

Cache entries have a configurable **Time-To-Live** (default 30 seconds).
If the cache file is missing, corrupted, or stale a full live detection
is triggered and the cache is refreshed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# ── Defaults ──────────────────────────────────────────────────────────────────

CACHE_DIR_NAME: str = ".ajo_cache"
CACHE_FILE_NAME: str = "detector_state.json"
DEFAULT_TTL: float = 30.0  # seconds


# ── Public API ────────────────────────────────────────────────────────────────


class DetectorCache:
    """Filesystem-backed cache for :class:`~ajo.detector.project.DjangoProjectDetector`.

    Usage::

        from ajo.detector.cache import DetectorCache

        cache = DetectorCache(project_path)
        if cache.is_fresh():
            state = cache.load()
        else:
            state = await run_live_detection()
            cache.save(state)

    Args:
        project_path: Root directory of the Django project (where
            ``manage.py`` lives).
        ttl: Maximum age of a cache entry in seconds before it is
            considered stale.
    """

    def __init__(self, project_path: Path, *, ttl: float = DEFAULT_TTL) -> None:
        self._project_path = project_path.resolve()
        self._ttl = ttl
        self._cache_dir = self._project_path / CACHE_DIR_NAME
        self._cache_file = self._cache_dir / CACHE_FILE_NAME

    # ── Public methods ───────────────────────────────────────────────────

    @property
    def cache_path(self) -> Path:
        """Full path to the cache file (read-only)."""
        return self._cache_file

    def is_fresh(self) -> bool:
        """Check whether a valid, non-expired cache exists.

        Returns ``True`` if the cache file exists, is valid JSON, and
        was written less than ``ttl`` seconds ago.  Corrupted files
        are treated as stale.
        """
        if not self._cache_file.exists():
            return False

        try:
            age = time.time() - self._cache_file.stat().st_mtime
            if age > self._ttl:
                return False

            # Quick validity check — parse the header only.
            with self._cache_file.open("rb") as fh:
                header = fh.read(64)
            # The file must start with '{' (valid JSON object).
            return header.lstrip().startswith(b"{")

        except (OSError, json.JSONDecodeError):
            return False

    def load(self) -> dict[str, Any] | None:
        """Load cached detector state.

        Returns:
            The deserialised state dictionary, or ``None`` if the cache
            is missing, stale, or corrupted.
        """
        if not self.is_fresh():
            return None

        try:
            raw = self._cache_file.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
            return data
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return None

    def save(self, state: dict[str, Any]) -> bool:
        """Persist detector *state* to the cache file.

        Creates the ``.ajo_cache/`` directory if it does not exist.

        Returns:
            ``True`` if the write succeeded, ``False`` otherwise.
        """
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(
                json.dumps(state, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except (OSError, PermissionError):
            return False

    def invalidate(self) -> bool:
        """Delete the cache file, forcing a live fetch on next access.

        Returns:
            ``True`` if the file was removed (or did not exist).
        """
        try:
            if self._cache_file.exists():
                self._cache_file.unlink()
            return True
        except OSError:
            return False

    @property
    def age(self) -> float | None:
        """Age of the cache in seconds, or ``None`` if it does not exist."""
        try:
            return time.time() - self._cache_file.stat().st_mtime
        except FileNotFoundError:
            return None
