"""Integration tests for add-on rollback on failure.

Verifies that if an add-on's ``apply()`` raises an exception, the
engine's rollback mechanism cleans up generated files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ajo.core.exceptions import PresetError, RollbackError
from ajo.presets.addons import ADDON_REGISTRY, AbstractAddon, register_addon
from ajo.scaffolding.engine import RollbackManager, ScaffoldEngine


# ── Failing add-on for rollback tests ─────────────────────────────────
# We register once at import time and clean up with a fixture.


class FailingAddon(AbstractAddon):
    """An add-on that always fails during apply()."""

    name = "Failing Addon"
    description = "This add-on intentionally fails"

    async def apply(
        self,
        project_path: Path,
        project_name: str,
        env_config: dict[str, Any],
    ) -> None:
        # Create a file first (to test rollback), then fail
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "FAILED_MARKER").write_text("created before failure")
        raise PresetError("Intentional failure for rollback test")


# Register for the test session
if "failing" not in ADDON_REGISTRY:
    register_addon(FailingAddon)


@pytest.fixture(autouse=True)
def _cleanup_failing_addon():
    """Remove ``failing`` add-on from registry after each test
    so it doesn't pollute other test files."""
    yield
    ADDON_REGISTRY.pop("failing", None)


# ── RollbackManager Unit Tests ────────────────────────────────────────


class TestRollbackManager:
    """Unit tests for :class:`RollbackManager`."""

    def test_push_and_execute(self) -> None:
        rb = RollbackManager()
        marker = []

        rb.push("append marker", lambda: marker.append("undone"))
        rb.execute_all()

        assert marker == ["undone"]

    def test_lifo_order(self) -> None:
        rb = RollbackManager()
        order: list[int] = []

        rb.push("first", lambda: order.append(1))
        rb.push("second", lambda: order.append(2))
        rb.execute_all()

        assert order == [2, 1]  # LIFO

    def test_empty_stack_execute(self) -> None:
        rb = RollbackManager()
        rb.execute_all()  # Should not raise

    def test_has_actions(self) -> None:
        rb = RollbackManager()
        assert not rb.has_actions
        rb.push("test", lambda: None)
        assert rb.has_actions

    def test_len(self) -> None:
        rb = RollbackManager()
        assert len(rb) == 0
        rb.push("test", lambda: None)
        assert len(rb) == 1

    def test_rollback_manager_with_error(self) -> None:
        """RollbackManager should collect errors and raise RollbackError."""
        rb = RollbackManager()
        rb.push("failing action", lambda: (_ for _ in ()).throw(ValueError("boom")))
        rb.push("good action", lambda: None)

        with pytest.raises(RollbackError, match="boom"):
            rb.execute_all()


# ── Add-on Rollback Integration Tests ──────────────────────────────────


@pytest.mark.asyncio
class TestAddonRollback:
    """Add-on failure and rollback behaviour."""

    async def test_failing_addon_raises(
        self, temp_project: Path, env_config: dict
    ) -> None:
        from ajo.presets.addons import resolve_addons

        # Re-register if cleanup removed it
        if "failing" not in ADDON_REGISTRY:
            register_addon(FailingAddon)

        addons = resolve_addons(["failing"])
        with pytest.raises(PresetError, match="Intentional failure"):
            for addon in addons:
                await addon.apply(temp_project, "test_project", env_config)

        # The file created before failure should still exist
        marker = temp_project / "FAILED_MARKER"
        assert marker.exists()

    async def test_engine_step_addon_propagates_error(self, tmp_path: Path) -> None:
        """When _step_addon fails, ScaffoldEngine should propagate."""
        from ajo.presets.addons import resolve_addons

        if "failing" not in ADDON_REGISTRY:
            register_addon(FailingAddon)

        project_path = tmp_path / "rollback_test"
        env_config = {
            "project_name": "rollback_test",
            "db_type": "sqlite",
            "db_config": {},
            "preset_key": "monolith",
        }

        engine = ScaffoldEngine(project_path, env_config=env_config)
        addons = resolve_addons(["failing"])

        # The engine wraps the error message in _step_addon
        with pytest.raises(PresetError, match="apply failed|Intentional failure"):
            await engine._step_addon(addons)
