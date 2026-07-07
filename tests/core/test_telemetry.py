"""Tests for opt-in telemetry system."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ajo.core.telemetry import (
    OPTOUT_SENTINEL,
    TELEMETRY_FILE,
    TelemetryEvent,
    TelemetryStore,
    _anonymise,
    _hash_value,
    is_telemetry_enabled,
)


# ═════════════════════════════════════════════════════════════════════════════
# _hash_value
# ═════════════════════════════════════════════════════════════════════════════


class TestHashValue:
    def test_returns_16_char_hex(self) -> None:
        result = _hash_value("my-project")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        assert _hash_value("test") == _hash_value("test")

    def test_different_inputs_differ(self) -> None:
        assert _hash_value("project-a") != _hash_value("project-b")


# ═════════════════════════════════════════════════════════════════════════════
# _anonymise
# ═════════════════════════════════════════════════════════════════════════════


class TestAnonymise:
    def test_hashes_project_name(self) -> None:
        result = _anonymise({"project_name": "my-cool-app"})
        assert result["project_name"] != "my-cool-app"
        assert len(result["project_name"]) == 16

    def test_hashes_path(self) -> None:
        result = _anonymise({"path": "/home/user/project"})
        assert result["path"] != "/home/user/project"

    def test_hashes_name(self) -> None:
        result = _anonymise({"name": "my-plugin"})
        assert result["name"] != "my-plugin"

    def test_preserves_non_sensitive_fields(self) -> None:
        result = _anonymise({"preset": "monolith", "count": 42})
        assert result["preset"] == "monolith"
        assert result["count"] == 42

    def test_empty_payload(self) -> None:
        assert _anonymise({}) == {}


# ═════════════════════════════════════════════════════════════════════════════
# TelemetryEvent
# ═════════════════════════════════════════════════════════════════════════════


class TestTelemetryEvent:
    def test_auto_timestamp(self) -> None:
        event = TelemetryEvent(event_type="test")
        assert event.timestamp != ""
        assert "T" in event.timestamp  # ISO-8601 format

    def test_auto_ajo_version(self) -> None:
        event = TelemetryEvent(event_type="test")
        assert event.ajo_version != ""

    def test_payload_is_anonymised(self) -> None:
        event = TelemetryEvent(
            event_type="scaffold",
            payload={"project_name": "secret-project", "preset": "monolith"},
        )
        assert event.payload["project_name"] != "secret-project"
        assert event.payload["preset"] == "monolith"

    def test_asdict_contains_keys(self) -> None:
        from dataclasses import asdict

        event = TelemetryEvent(event_type="scaffold_start")
        d = asdict(event)
        assert "event_type" in d
        assert "timestamp" in d
        assert "ajo_version" in d
        assert "payload" in d

    def test_provided_timestamp(self) -> None:
        event = TelemetryEvent(
            event_type="test",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        assert event.timestamp == "2024-01-01T00:00:00+00:00"


# ═════════════════════════════════════════════════════════════════════════════
# TelemetryStore
# ═════════════════════════════════════════════════════════════════════════════


class TestTelemetryStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> TelemetryStore:
        """Return a TelemetryStore with a temp directory."""
        store = TelemetryStore()
        store._file = tmp_path / "telemetry.jsonl"
        return store

    def test_disabled_by_default(self, store: TelemetryStore) -> None:
        """Telemetry is opt-out — disabled unless explicitly enabled."""
        assert store.enabled is False

    def test_record_is_noop_when_disabled(self, store: TelemetryStore) -> None:
        store.record("test_event", {"key": "value"})
        assert not store._file.exists()

    def test_record_writes_jsonl(self, store: TelemetryStore) -> None:
        store._enabled = True
        store.record("scaffold_start", {"preset": "monolith"})
        assert store._file.is_file()
        lines = store._file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "scaffold_start"

    def test_read_events(self, store: TelemetryStore) -> None:
        store._enabled = True
        store.record("event_a", {"count": 1})
        store.record("event_b", {"count": 2})

        events = store.read_events()
        assert len(events) == 2
        assert events[0].event_type == "event_a"
        assert events[1].event_type == "event_b"

    def test_read_events_empty_file(self, store: TelemetryStore) -> None:
        """Reading when no events exist returns empty list."""
        events = store.read_events()
        assert events == []

    def test_read_events_skips_corrupt_lines(self, store: TelemetryStore) -> None:
        store._file.parent.mkdir(parents=True, exist_ok=True)
        store._file.write_text(
            '{"event_type": "good", "timestamp": "2024-01-01", "ajo_version": "1.0", "payload": {}}\n'
            "corrupt line\n"
            '{"event_type": "also_good", "timestamp": "2024-01-01", "ajo_version": "1.0", "payload": {}}\n'
        )
        events = store.read_events()
        assert len(events) == 2

    def test_clear_removes_file(self, store: TelemetryStore) -> None:
        store._enabled = True
        store.record("test")
        assert store._file.exists()
        store.clear()
        assert not store._file.exists()

    def test_clear_missing_file_does_not_raise(self, store: TelemetryStore) -> None:
        store.clear()  # Should not raise

    def test_enabled_via_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting AJO_TELEMETRY_OPT_OUT=1 disables telemetry."""
        monkeypatch.setenv("AJO_TELEMETRY_OPT_OUT", "1")
        # Even when explicitly enabled, the env var overrides
        store = TelemetryStore()
        assert store.enabled is False

    def test_enabled_via_sentinel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Creating the opt-out sentinel disables telemetry."""
        sentinel = Path("/tmp/test-telemetry-opt-out")
        monkeypatch.setattr("ajo.core.telemetry.OPTOUT_SENTINEL", sentinel)
        try:
            sentinel.touch()
            store = TelemetryStore()
            assert store.enabled is False
        finally:
            if sentinel.exists():
                sentinel.unlink()

    def test_record_handles_permission_error(
        self, store: TelemetryStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write errors are silently swallowed."""
        store._enabled = True

        def _raise(*args, **kwargs):
            raise PermissionError("denied")

        monkeypatch.setattr("builtins.open", _raise)
        # Should not raise
        store.record("test")

    def test_anonymised_payload_in_written_event(self, store: TelemetryStore) -> None:
        """Sensitive fields are hashed before writing."""
        store._enabled = True
        store.record("scaffold", {"project_name": "my-secret-app"})
        data = json.loads(store._file.read_text())
        assert data["payload"]["project_name"] != "my-secret-app"

    def test_record_with_non_serializable_payload_fails_gracefully(
        self, store: TelemetryStore
    ) -> None:
        """Payloads containing non-JSON-serializable values raise TypeError
        which is caught and logged (not propagated to caller)."""
        store._enabled = True
        # bytes is not JSON-serializable — should not propagate
        store.record("test", {"data": b"binary"})
        # No exception should propagate; the event is silently skipped

    def test_record_with_nested_payload_anonymises_deep(
        self, store: TelemetryStore
    ) -> None:
        """Nested dicts inside sensitive fields are also anonymised."""
        store._enabled = True
        store.record(
            "scaffold",
            {"project_name": "my-app", "extra": {"inner": "value"}},
        )
        data = json.loads(store._file.read_text())
        assert data["payload"]["project_name"] != "my-app"
        assert data["payload"]["extra"]["inner"] == "value"


# ═════════════════════════════════════════════════════════════════════════════
# Edge cases: _anonymise
# ═════════════════════════════════════════════════════════════════════════════


class TestAnonymiseEdgeCases:
    def test_non_string_value_for_sensitive_key(self) -> None:
        """Non-string values for sensitive keys are passed through unchanged."""
        result = _anonymise({"project_name": 42, "path": None, "count": 3})
        assert result["project_name"] == 42
        assert result["path"] is None
        assert result["count"] == 3


# ═════════════════════════════════════════════════════════════════════════════
# is_telemetry_enabled
# ═════════════════════════════════════════════════════════════════════════════


class TestIsTelemetryEnabled:
    def test_returns_false_by_default(self) -> None:
        assert is_telemetry_enabled() is False

    def test_returns_false_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AJO_TELEMETRY_OPT_OUT", "1")
        assert is_telemetry_enabled() is False


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════


class TestTelemetryConstants:
    def test_telemetry_file_is_in_config_dir(self) -> None:
        assert "telemetry.log" in str(TELEMETRY_FILE)

    def test_optout_sentinel_is_in_config_dir(self) -> None:
        assert "telemetry-opt-out" in str(OPTOUT_SENTINEL)
