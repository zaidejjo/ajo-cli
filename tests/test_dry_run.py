"""Tests for --dry-run flag on scaffold.

Verifies that:
1. ``--dry-run`` is recognised by the argument parser.
2. ``ScaffoldEngine.execute(dry_run=True)`` logs steps but does not create files.
3. Dry-run output includes preview files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest import mock

import pytest

from ajo.scaffolding.engine import ScaffoldEngine


# =============================================================================
# Parser
# =============================================================================


class TestDryRunFlagParsing:
    """The --dry-run flag is recognised by the argument parser."""

    def test_dry_run_default_is_false(self) -> None:
        from ajo.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False

    def test_dry_run_flag_sets_true(self) -> None:
        from ajo.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_dry_run_with_headless(self) -> None:
        from ajo.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--dry-run", "--yes", "--name", "testproj"])
        assert args.dry_run is True
        assert args.yes is True
        assert args.name == "testproj"


# =============================================================================
# ScaffoldEngine dry_run
# =============================================================================


class TestScaffoldEngineDryRun:
    """ScaffoldEngine.execute(dry_run=True) does not create files."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_true(self, tmp_path: Path) -> None:
        """dry_run execution returns True immediately."""
        engine = ScaffoldEngine(tmp_path / "myproject")
        result = await engine.execute(dry_run=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_dry_run_does_not_create_directory(self, tmp_path: Path) -> None:
        """dry_run should NOT create the project directory."""
        project_dir = tmp_path / "myproject"
        engine = ScaffoldEngine(project_dir)
        await engine.execute(dry_run=True)
        assert not project_dir.exists(), (
            "Dry run created the project directory despite --dry-run"
        )

    @pytest.mark.asyncio
    async def test_dry_run_with_preset_does_not_scaffold(
        self,
        tmp_path: Path,
    ) -> None:
        """dry_run with a preset does not call scaffold()."""
        mock_preset = mock.MagicMock()
        mock_preset.name = "Test Preset"
        mock_preset.dependencies = []
        mock_preset.dev_dependencies = []
        mock_preset.scaffold = mock.AsyncMock()

        engine = ScaffoldEngine(tmp_path / "myproject")
        await engine.execute(preset=mock_preset, dry_run=True)

        # scaffold should NOT have been called
        mock_preset.scaffold.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dry_run_with_addons_does_not_apply(
        self,
        tmp_path: Path,
    ) -> None:
        """dry_run with add-ons does not call apply()."""
        mock_addon = mock.MagicMock()
        mock_addon.name = "Test Addon"
        mock_addon.dependencies = []
        mock_addon.dev_dependencies = []
        mock_addon.apply = mock.AsyncMock()

        engine = ScaffoldEngine(tmp_path / "myproject")
        await engine.execute(addons=[mock_addon], dry_run=True)

        mock_addon.apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dry_run_logs_steps(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:  # noqa: E501
        """dry_run logs each step at INFO level with [DRY RUN] prefix."""
        caplog.set_level(logging.INFO)

        mock_preset = mock.MagicMock()
        mock_preset.name = "Test Preset"
        mock_preset.dependencies = []
        mock_preset.dev_dependencies = []

        engine = ScaffoldEngine(tmp_path / "myproject")
        await engine.execute(preset=mock_preset, dry_run=True)

        dry_run_logs = [r for r in caplog.records if "[DRY RUN]" in r.getMessage()]
        assert len(dry_run_logs) > 0, "No [DRY RUN] log messages found"
        assert any("Creating project directory" in r.getMessage() for r in dry_run_logs)
        assert any("Creating .env file" in r.getMessage() for r in dry_run_logs)
        assert any("Running Test Preset preset" in r.getMessage() for r in dry_run_logs)

    @pytest.mark.asyncio
    async def test_dry_run_preview_files_available(self, tmp_path: Path) -> None:
        """get_preview_files() returns entries even in dry-run mode."""
        engine = ScaffoldEngine(tmp_path / "myproject")
        # Call get_preview_files directly — it doesn't depend on execution
        files = engine.get_preview_files()
        # At minimum: project dir, .env, .gitignore, pyproject.toml
        assert len(files) >= 4
        paths = [p for p, _ in files]
        assert any("myproject/" in p for p in paths)
        assert any(".env" in p for p in paths)


# =============================================================================
# Integration: _show_dry_run_plan
# =============================================================================


class TestShowDryRunPlan:
    """_show_dry_run_plan returns 0 and does not raise."""

    def test_show_dry_run_plan_returns_zero(self) -> None:
        """_show_dry_run_plan returns exit code 0."""
        from ajo.cli import _show_dry_run_plan

        from ajo.presets import get_preset

        preset_cls = get_preset("monolith")
        preset_instance = preset_cls()
        engine = ScaffoldEngine(Path("/tmp/nonexistent_dry_run_test"))

        result = _show_dry_run_plan(
            engine=engine,
            preset=preset_instance,
            addons=None,
            preset_key="monolith",
            database="sqlite",
            project_name="testproj",
            project_path=Path("/tmp/nonexistent_dry_run_test"),
        )
        assert result == 0
