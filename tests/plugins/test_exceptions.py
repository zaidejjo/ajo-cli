"""Tests for plugin error propagation and exception hierarchy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from rich.console import Console

from ajo.core.exceptions import AjoError
from ajo.plugins.exceptions import (
    PluginDiscoveryError,
    PluginError,
    PluginHookError,
    PluginValidationError,
    PluginVersionError,
)
from ajo.plugins.hooks import PluginManager, _load_hook_callable
from ajo.plugins.manifest import PluginManifest
from tests.plugins.test_hooks import _FakeDiscovery


# ═════════════════════════════════════════════════════════════════════════════
# Exception hierarchy integrity
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginErrorIsAjoError:
    """All plugin errors must inherit from AjoError so top-level handlers
    in the CLI can catch them uniformly."""

    def test_plugin_error_is_ajo_error(self) -> None:
        assert issubclass(PluginError, AjoError)

    def test_discovery_error_is_plugin_error(self) -> None:
        assert issubclass(PluginDiscoveryError, PluginError)

    def test_validation_error_is_plugin_error(self) -> None:
        assert issubclass(PluginValidationError, PluginError)

    def test_version_error_is_plugin_error(self) -> None:
        assert issubclass(PluginVersionError, PluginValidationError)

    def test_hook_error_is_plugin_error(self) -> None:
        assert issubclass(PluginHookError, PluginError)


# ═════════════════════════════════════════════════════════════════════════════
# PluginError
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginErrorBase:
    def test_message_is_stored(self) -> None:
        err = PluginError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"

    def test_empty_message(self) -> None:
        err = PluginError()
        assert str(err) == ""


# ═════════════════════════════════════════════════════════════════════════════
# PluginDiscoveryError
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginDiscoveryError:
    def test_with_path(self) -> None:
        err = PluginDiscoveryError("permission denied", path="/some/addon")
        assert err.path == "/some/addon"
        assert "permission denied" in str(err)

    def test_without_path(self) -> None:
        err = PluginDiscoveryError("unknown error")
        assert err.path is None

    def test_raised_by_discovery_on_invalid_manifest(self, tmp_path: Path) -> None:
        """When discovery encounters an invalid manifest, errors should
        contain the path to the plugin directory."""
        global_dir = tmp_path / "addons"
        bad_dir = global_dir / "bad-plugin"
        bad_dir.mkdir(parents=True)
        (bad_dir / "addon.json").write_text("{invalid json}")

        from ajo.plugins.discovery import PluginDiscovery

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        assert len(result.errors) >= 1
        err = result.errors[0]
        assert isinstance(err, PluginDiscoveryError)
        assert err.path is not None
        assert "bad-plugin" in err.path or "Invalid JSON" in str(err)


# ═════════════════════════════════════════════════════════════════════════════
# PluginValidationError
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginValidationError:
    def test_with_reasons(self) -> None:
        err = PluginValidationError(
            "invalid manifest",
            path="/path/addon.json",
            plugin_name="my-plugin",
            reasons=["Missing field 'version'", "Wrong type for 'name'"],
        )
        assert err.path == "/path/addon.json"
        assert err.plugin_name == "my-plugin"
        assert len(err.reasons) == 2

    def test_from_validator_on_missing_fields(self) -> None:
        """ManifestValidator passes validation errors with reasons."""
        from ajo.plugins.manifest import ManifestValidator

        validator = ManifestValidator()
        raw = json.dumps({"name": "test-plugin"})  # missing version, description
        _, errors = validator.loads(raw)
        assert len(errors) >= 1
        err = errors[0]
        assert isinstance(err, PluginValidationError)
        assert err.reasons is not None


# ═════════════════════════════════════════════════════════════════════════════
# PluginVersionError
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginVersionError:
    def test_version_mismatch_message(self) -> None:
        err = PluginVersionError(
            "Plugin requires ajo version ≥ 99.0.0, current is 3.3.0",
            path="/plugin/addon.json",
        )
        assert "99.0.0" in str(err)
        assert "3.3.0" in str(err)

    def test_is_validation_error(self) -> None:
        assert isinstance(PluginVersionError("msg"), PluginValidationError)


# ═════════════════════════════════════════════════════════════════════════════
# PluginHookError
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginHookError:
    def test_with_all_attributes(self) -> None:
        original = ValueError("something broke")
        err = PluginHookError(
            "hook failed",
            plugin_name="my-plugin",
            hook_type="pre_scaffold",
            original=original,
        )
        assert err.plugin_name == "my-plugin"
        assert err.hook_type == "pre_scaffold"
        assert err.original is original

    def test_from_hook_failure(self, tmp_path: Path) -> None:
        """A hook error raised by PluginManager preserves plugin name
        and hook type."""
        plugin_dir = tmp_path / "fail-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    raise RuntimeError("epic fail")
""")
        manifest = PluginManifest(
            name="fail-plugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        mgr.load_all()

        import asyncio

        errors = asyncio.run(mgr.execute_pre_scaffold(tmp_path, {}))
        assert len(errors) == 1
        err = errors[0]
        assert isinstance(err, PluginHookError)
        assert err.plugin_name == "fail-plugin"
        assert err.hook_type == "pre_scaffold"
        assert isinstance(err.original, RuntimeError)
        assert "epic fail" in str(err)


# ═════════════════════════════════════════════════════════════════════════════
# Propagation in ScaffoldEngine
# ═════════════════════════════════════════════════════════════════════════════


class TestScaffoldPropagation:
    """Plugin errors during scaffold should be caught and reported as
    PresetError (which is the existing scaffold error mechanism)."""

    @pytest.mark.asyncio
    async def test_pre_hook_failure_returns_false(self, tmp_path: Path) -> None:
        """A failing pre-scaffold hook causes scaffold to return False."""
        plugin_dir = tmp_path / "bad-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    raise RuntimeError("hook died")
""")
        manifest = PluginManifest(
            name="bad-plugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        mgr.load_all()

        from ajo.scaffolding.engine import ScaffoldEngine

        engine = ScaffoldEngine(
            tmp_path / "output",
            env_config={"project_name": "testproj"},
            plugin_manager=mgr,
        )
        # Without a preset, only hooks run — pre_hooks step should fail
        result = await engine.execute()
        assert result is False

    def test_hook_error_message_includes_plugin_name(self, tmp_path: Path) -> None:
        """The error message from hook failure mentions the plugin name."""
        plugin_dir = tmp_path / "named-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    raise ValueError("oops")
""")
        manifest = PluginManifest(
            name="named-plugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        mgr.load_all()

        import asyncio

        errors = asyncio.run(mgr.execute_pre_scaffold(tmp_path, {}))
        assert len(errors) == 1
        msg = str(errors[0])
        assert "named-plugin" in msg
        assert "pre_scaffold" in msg
        assert "oops" in msg


# ═════════════════════════════════════════════════════════════════════════════
# Error display (Rich integration)
# ═════════════════════════════════════════════════════════════════════════════


class TestErrorDisplay:
    """Ensure AjoError-based plugin errors render well through
    the existing show_error mechanism."""

    def test_plugin_error_renders_via_show_error(
        self, capsys: CaptureFixture[str]
    ) -> None:
        """A PluginError should be displayable by the CLI's error handler.
        We simulate what happens when the CLI catches an AjoError.
        """
        from ajo.cli import show_error

        err = PluginHookError(
            "Plugin 'my-plugin' pre_scaffold hook failed: boom",
            plugin_name="my-plugin",
            hook_type="pre_scaffold",
        )

        # show_error uses rich console; capture the output
        show_error("Plugin Error", str(err))
        captured = capsys.readouterr()
        # Should contain the error message (Rich formatting may add ANSI codes)
        assert "my-plugin" in captured.out or "my-plugin" in captured.err


# ═════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_discovery_error_no_manifest(self, tmp_path: Path) -> None:
        """A directory without addon.json produces discovery error."""
        from ajo.plugins.discovery import PluginDiscovery

        global_dir = tmp_path / "addons"
        empty_plugin = global_dir / "empty-plugin"
        empty_plugin.mkdir(parents=True)
        # No addon.json at all

        discovery = PluginDiscovery(
            global_dir=global_dir,
            project_dir=tmp_path / "nonexistent",
        )
        result = discovery.scan()
        # empty-plugin should not appear in manifests (no addon.json)
        names = [m.name for m in result.manifests]
        assert "empty-plugin" not in names
        # It should be an error (missing addon.json)
        assert len(result.errors) >= 1

    def test_validation_error_preserves_path(self) -> None:
        from ajo.plugins.manifest import ManifestValidator

        validator = ManifestValidator()
        _, errors = validator.loads(
            json.dumps({"name": "x", "version": "1.0"}),
            source_path="/custom/path/addon.json",
        )
        # Missing description
        for err in errors:
            assert err.path == "/custom/path/addon.json"

    def test_hook_error_original_exception_chain(self) -> None:
        """The original exception is preserved in PluginHookError."""
        try:
            try:
                raise ValueError("inner failure")
            except ValueError as inner:
                raise PluginHookError(
                    "hook failed",
                    plugin_name="p",
                    hook_type="pre_scaffold",
                    original=inner,
                ) from inner
        except PluginHookError as exc:
            assert exc.original is not None
            assert isinstance(exc.original, ValueError)
            assert str(exc.original) == "inner failure"
            # __cause__ should be set
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)
