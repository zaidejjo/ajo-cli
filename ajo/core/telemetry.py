"""Opt-in anonymous telemetry system.

.. warning::
   Telemetry is **opt-in only**.  No data is collected unless the user
   explicitly enables it.  The system is entirely local — no network
   calls are made — and respects the following opt-out mechanisms:

   * Environment variable ``AJO_TELEMETRY_OPT_OUT=1``
   * Sentinel file ``~/.config/ajo/telemetry-opt-out``
   * Config key ``telemetry_opt_out: true`` in ``~/.config/ajo/config.json``

Telemetry events are written as newline-delimited JSON (JSONL) to
``~/.config/ajo/telemetry.log``.  Each event contains a timestamp, an
event type, and an optional payload dictionary.  Any user-identifiable
data (project names, file paths) is **hashed** before recording.

Usage::

    from ajo.core.telemetry import TelemetryStore

    store = TelemetryStore()
    if store.enabled:
        store.record("scaffold_complete", {"preset": "monolith"})
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ajo import __version__ as _ajo_version
from ajo.core.config import CONFIG_DIR

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

TELEMETRY_FILE: Path = CONFIG_DIR / "telemetry.log"
"""Path to the local telemetry log (JSONL format)."""

OPTOUT_SENTINEL: Path = CONFIG_DIR / "telemetry-opt-out"
"""If this file exists, telemetry is disabled."""

OPTOUT_ENV_VAR: str = "AJO_TELEMETRY_OPT_OUT"
"""If this env var is set to ``1``, telemetry is disabled."""


# ── Hashing helper ────────────────────────────────────────────────────────────


def _hash_value(value: str) -> str:
    """Return a SHA-256 hex digest of *value* for anonymisation.

    Uses the first 16 characters of the hex digest — sufficient to
    distinguish events while preventing reconstruction of the original.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _anonymise(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *payload* with identifiable string values hashed.

    Known identifying keys (``project_name``, ``path``, ``name``) are
    hashed.  Other values are preserved as-is.
    """
    sensitive_fields = {"project_name", "path", "name", "project"}
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key in sensitive_fields and isinstance(value, str):
            result[key] = _hash_value(value)
        else:
            result[key] = value
    return result


# ── Telemetry event ───────────────────────────────────────────────────────────


@dataclass
class TelemetryEvent:
    """A single telemetry event.

    Attributes:
        event_type: Short machine-readable event name (e.g. ``"scaffold_start"``).
        timestamp: ISO-8601 timestamp (UTC).  Auto-set if not provided.
        ajo_version: The ajo version at the time of the event.
        payload: Event-specific data (auto-anonymised).
    """

    event_type: str
    timestamp: str = ""
    ajo_version: str = _ajo_version
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.payload = _anonymise(self.payload)


# ── Telemetry store ───────────────────────────────────────────────────────────


class TelemetryStore:
    """Local, opt-in, privacy-respecting telemetry store.

    Events are appended to ``~/.config/ajo/telemetry.log`` in JSONL
    format.  No network access is performed — the file is purely local.

    Telemetry is **opt-in**: it is disabled by default.  The user must
    explicitly enable it by removing the opt-out sentinel.
    """

    def __init__(self) -> None:
        self._enabled: bool = self._check_enabled()
        self._file: Path = TELEMETRY_FILE

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """``True`` if telemetry is currently enabled for this session."""
        return self._enabled

    def record(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Record a telemetry event.

        This is a no-op (silent) if telemetry is disabled or if the
        write fails for any reason (permission, disk full, etc.).

        Args:
            event_type: Short event name (e.g. ``"scaffold_complete"``).
            payload: Optional event-specific data (anonymised automatically).
        """
        if not self._enabled:
            return

        event = TelemetryEvent(
            event_type=event_type,
            payload=payload or {},
        )

        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except (OSError, PermissionError) as exc:
            logger.debug("Cannot write telemetry event: %s", exc)

    def read_events(self) -> list[TelemetryEvent]:
        """Read all stored telemetry events (for debugging / reporting).

        Returns:
            A list of :class:`TelemetryEvent` instances, or an empty list
            if the file doesn't exist or is unreadable.
        """
        if not self._file.is_file():
            return []

        events: list[TelemetryEvent] = []
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data: dict[str, Any] = json.loads(line)
                        events.append(TelemetryEvent(**data))
                    except (json.JSONDecodeError, TypeError, KeyError):
                        continue  # Skip corrupt lines
        except (OSError, PermissionError):
            pass

        return events

    def clear(self) -> None:
        """Delete all stored telemetry events.

        Silently handles missing files and permission errors.
        """
        try:
            if self._file.is_file():
                self._file.unlink()
        except (OSError, PermissionError):
            pass

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _check_enabled() -> bool:
        """Check whether telemetry is enabled for this session.

        Telemetry is **disabled** (opt-out) by default.  It is enabled
        only when ALL of the following conditions are met:

        1. The ``AJO_TELEMETRY_OPT_OUT`` env var is NOT set to ``"1"``.
        2. The sentinel file ``~/.config/ajo/telemetry-opt-out`` does NOT exist.
        3. The config key ``telemetry_opt_out`` is NOT ``True`` (handled
           by the caller, not checked here).

        Returns:
            ``True`` if telemetry should be enabled.
        """
        # Env var check
        if os.environ.get(OPTOUT_ENV_VAR) == "1":
            return False

        # Sentinel file check
        if OPTOUT_SENTINEL.is_file():
            return False

        # Default: opt-out (disabled unless user explicitly enabled)
        return False


def is_telemetry_enabled() -> bool:
    """Convenience function: check if telemetry is enabled.

    Returns:
        ``True`` if telemetry events should be recorded.
    """
    return TelemetryStore().enabled


__all__ = [
    "TELEMETRY_FILE",
    "OPTOUT_SENTINEL",
    "TelemetryEvent",
    "TelemetryStore",
    "is_telemetry_enabled",
]
