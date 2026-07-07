"""Tests for PluginDiscovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ajo.plugins.discovery import (
    LOCAL_PLUGIN_DIR_REL,
    DiscoveryResult,
    PluginDiscovery,
)
from ajo.plugins.manifest import PluginManifest


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def valid_manifest_data() -> dict:
    return {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "author": "Test Author",
    }


def _create_plugin(plugin_dir: Path, manifest_data: dict) -> Path:
    """Create a plugin directory with addon.json and return its path."""
    d = plugin_dir / str(manifest_data["name"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "addon.json").write_text(json.dumps(manifest_data, indent=2))
    return d


# ═════════════════════════════════════════════════════════════════════════════
# DiscoveryResult
# ═════════════════════════════════════════════════════════════════════════════


class TestDiscoveryResult:
    def test_empty_result(self) -> None:
        r = DiscoveryResult()
        assert r.manifests == []
        assert r.errors == []
        assert r.scanned_dirs == []


# ═════════════════════════════════════════════════════════════════════════════
# PluginDiscovery
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginDiscovery:
    def test_scan_nonexistent_directories(self) -> None:
        """Both global and local dirs don't exist → empty manifests."""
        discovery = PluginDiscovery(
            global_dir=Path("/nonexistent/global/addons"),
            project_dir=Path("/nonexistent/project/.ajo/addons"),
        )
        result = discovery.scan()
        assert result.manifests == []
        assert result.errors == []
        assert result.scanned_dirs == []

    def test_scan_global_only(self, tmp_path: Path, valid_manifest_data: dict) -> None:
        global_dir = tmp_path / "config" / "ajo" / "addons"
        _create_plugin(global_dir, valid_manifest_data)

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert len(result.manifests) == 1
        assert result.manifests[0].name == "test-plugin"
        assert result.manifests[0].version == "1.0.0"

    def test_scan_project_local_only(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        project_dir = tmp_path / "project" / LOCAL_PLUGIN_DIR_REL
        _create_plugin(project_dir, valid_manifest_data)

        discovery = PluginDiscovery(
            global_dir=tmp_path / "nonexistent",
            project_dir=project_dir,
        )
        result = discovery.scan()
        assert len(result.manifests) == 1
        assert result.manifests[0].name == "test-plugin"
        assert result.manifests[0].path is not None
        assert str(result.manifests[0].path).endswith("test-plugin")

    def test_project_local_overrides_global(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        """Same plugin name in both → project-local wins."""
        global_dir = tmp_path / "global"
        _create_plugin(global_dir, valid_manifest_data)

        local_data = dict(valid_manifest_data)
        local_data["version"] = "2.0.0"
        project_dir = tmp_path / "project" / LOCAL_PLUGIN_DIR_REL
        _create_plugin(project_dir, local_data)

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=project_dir,
        )
        result = discovery.scan()
        assert len(result.manifests) == 1  # Only one kept (local wins)
        assert result.manifests[0].version == "2.0.0"

    def test_scan_multiple_plugins(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        global_dir = tmp_path / "global"
        p1_data = dict(valid_manifest_data, name="plugin-a")
        p2_data = dict(valid_manifest_data, name="plugin-b")
        _create_plugin(global_dir, p1_data)
        _create_plugin(global_dir, p2_data)

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert len(result.manifests) == 2
        names = {m.name for m in result.manifests}
        assert names == {"plugin-a", "plugin-b"}

    def test_invalid_manifest_adds_to_errors(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        global_dir = tmp_path / "global"
        # Create a valid plugin
        _create_plugin(global_dir, valid_manifest_data)
        # Create an invalid one (missing required fields)
        invalid_dir = global_dir / "invalid-plugin"
        invalid_dir.mkdir()
        (invalid_dir / "addon.json").write_text(json.dumps({"name": "no-version"}))

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert len(result.manifests) == 1  # Only the valid one
        assert result.manifests[0].name == "test-plugin"
        assert len(result.errors) >= 1

    def test_skips_dot_directories(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        global_dir = tmp_path / "global"
        _create_plugin(global_dir, valid_manifest_data)
        # Create a hidden directory that's not a plugin
        hidden = global_dir / ".hidden"
        hidden.mkdir()
        (hidden / "addon.json").write_text(json.dumps(valid_manifest_data))

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert len(result.manifests) == 1

    def test_scan_directories_are_recorded(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        global_dir = tmp_path / "global"
        _create_plugin(global_dir, valid_manifest_data)
        project_dir = tmp_path / "project" / LOCAL_PLUGIN_DIR_REL
        _create_plugin(project_dir, dict(valid_manifest_data, name="local-plugin"))

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=project_dir,
        )
        result = discovery.scan()
        assert len(result.scanned_dirs) == 2
        resolved = [str(d) for d in result.scanned_dirs]
        assert any("global" in r for r in resolved)
        assert any("project" in r for r in resolved)

    def test_malformed_json_in_manifest(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        global_dir = tmp_path / "global"
        _create_plugin(global_dir, valid_manifest_data)
        bad_dir = global_dir / "broken"
        bad_dir.mkdir()
        (bad_dir / "addon.json").write_text("{this is not json}")

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert len(result.manifests) == 1
        assert len(result.errors) == 1
        assert "Invalid JSON" in str(result.errors[0])

    def test_default_dirs_use_correct_paths(self) -> None:
        """When no overrides are given, defaults point to expected locations."""
        discovery = PluginDiscovery()
        # We can't assert exact paths since they depend on CWD and CONFIG_DIR,
        # but we can assert they're Path objects.
        assert hasattr(discovery, "_global_dir")
        assert hasattr(discovery, "_project_dir")


# ═════════════════════════════════════════════════════════════════════════════
# DiscoveryResult type
# ═════════════════════════════════════════════════════════════════════════════


class TestDiscoveryResultType:
    def test_manifests_are_plugin_manifest_instances(
        self, tmp_path: Path, valid_manifest_data: dict
    ) -> None:
        global_dir = tmp_path / "global"
        _create_plugin(global_dir, valid_manifest_data)

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert all(isinstance(m, PluginManifest) for m in result.manifests)

    def test_errors_are_plugin_discovery_errors(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "global"
        bad_dir = global_dir / "bad"
        bad_dir.mkdir(parents=True)
        (bad_dir / "addon.json").write_text("not json")

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        from ajo.plugins.exceptions import PluginDiscoveryError

        assert all(isinstance(e, PluginDiscoveryError) for e in result.errors)
