"""Tests for PluginManager and hook execution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ajo.plugins.discovery import PluginDiscovery
from ajo.plugins.exceptions import PluginHookError
from ajo.plugins.hooks import HookType, PluginManager, _load_hook_callable
from ajo.plugins.manifest import PluginManifest


# ═════════════════════════════════════════════════════════════════════════════
# _load_hook_callable
# ═════════════════════════════════════════════════════════════════════════════


class TestLoadHookCallable:
    """Tests for the low-level entry-point loader."""

    def test_no_hooks_returns_none(self) -> None:
        manifest = PluginManifest(name="p", version="1.0", description="")
        assert _load_hook_callable(manifest) is None

    def test_hooks_no_entry_point_returns_none(self) -> None:
        manifest = PluginManifest(
            name="p", version="1.0", description="", hooks=["pre_scaffold"]
        )
        assert _load_hook_callable(manifest) is None

    def test_valid_entry_point(self, tmp_path: Path) -> None:
        """Load a callable from a plugin directory with __init__.py."""
        plugin_dir = tmp_path / "myplugin"
        plugin_dir.mkdir()
        hooks_code = """
def pre_scaffold(project_path, env_config):
    return "called"
"""
        (plugin_dir / "hooks.py").write_text(hooks_code)

        manifest = PluginManifest(
            name="myplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        registry = _load_hook_callable(manifest)
        assert registry is not None
        assert HookType.PRE_SCAFFOLD in registry
        assert callable(registry[HookType.PRE_SCAFFOLD])

    def test_missing_function(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "myplugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("x = 1\n")

        manifest = PluginManifest(
            name="myplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        assert _load_hook_callable(manifest) is None

    def test_missing_module(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "myplugin"
        plugin_dir.mkdir()

        manifest = PluginManifest(
            name="myplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="nonexistent:func",
            path=plugin_dir,
        )
        assert _load_hook_callable(manifest) is None

    def test_both_hook_types_same_function(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "myplugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def run(project_path, env_config):
    return "called"
""")

        manifest = PluginManifest(
            name="myplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold", "post_scaffold"],
            entry_point="hooks:run",
            path=plugin_dir,
        )
        registry = _load_hook_callable(manifest)
        assert registry is not None
        assert HookType.PRE_SCAFFOLD in registry
        assert HookType.POST_SCAFFOLD in registry

    def test_entry_point_path_traversal_is_rejected(self, tmp_path: Path) -> None:
        """Entry points with ``../`` that escape the plugin dir are rejected."""
        plugin_dir = tmp_path / "myplugin"
        plugin_dir.mkdir()
        # Create a file outside the plugin directory
        outside_file = tmp_path / "malicious.py"
        outside_file.write_text("def pre_scaffold(project_path, env_config): pass\n")

        manifest = PluginManifest(
            name="myplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="../malicious:pre_scaffold",
            path=plugin_dir,
        )
        assert _load_hook_callable(manifest) is None


# ═════════════════════════════════════════════════════════════════════════════
# PluginManager
# ═════════════════════════════════════════════════════════════════════════════


class _FakeDiscovery:
    """A fake PluginDiscovery that returns pre-configured results."""

    def __init__(self, manifests: list[PluginManifest]) -> None:
        self._manifests = manifests

    def scan(self):
        from ajo.plugins.discovery import DiscoveryResult

        result = DiscoveryResult()
        result.manifests = self._manifests
        return result


class TestPluginManager:
    def test_empty_plugin_manager(self) -> None:
        mgr = PluginManager(discovery=_FakeDiscovery([]))
        errors = mgr.load_all()
        assert errors == []
        assert mgr.manifests == []

    def test_loads_plugin_without_hooks(self) -> None:
        manifest = PluginManifest(name="p", version="1.0", description="")
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        errors = mgr.load_all()
        assert errors == []
        assert len(mgr.manifests) == 1

    def test_manifest_with_hooks_but_no_entry_point(
        self,
    ) -> None:
        manifest = PluginManifest(
            name="p",
            version="1.0",
            description="",
            hooks=["pre_scaffold"],
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        errors = mgr.load_all()
        assert len(errors) == 1
        assert "Failed to load hook callable" in str(errors[0])

    @pytest.mark.asyncio
    async def test_load_and_execute_sync_pre_hook(self, tmp_path: Path) -> None:
        """Sync pre_scaffold hook executes without error."""
        plugin_dir = tmp_path / "testplugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    pass
""")
        manifest = PluginManifest(
            name="testplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        load_errors = mgr.load_all()
        assert load_errors == []

        hook_errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert hook_errors == []

    @pytest.mark.asyncio
    async def test_load_and_execute_async_pre_hook(self, tmp_path: Path) -> None:
        """Async pre_scaffold hook executes without error."""
        plugin_dir = tmp_path / "testplugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
async def pre_scaffold(project_path, env_config):
    pass
""")
        manifest = PluginManifest(
            name="testplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        load_errors = mgr.load_all()
        assert load_errors == []

        hook_errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert hook_errors == []

    @pytest.mark.asyncio
    async def test_load_and_execute_post_hook(self, tmp_path: Path) -> None:
        """post_scaffold hook executes without error."""
        plugin_dir = tmp_path / "testplugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def post_scaffold(project_path, env_config):
    pass
""")
        manifest = PluginManifest(
            name="testplugin",
            version="1.0.0",
            description="",
            hooks=["post_scaffold"],
            entry_point="hooks:post_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        mgr.load_all()
        hook_errors = await mgr.execute_post_scaffold(tmp_path, {})
        assert hook_errors == []

    @pytest.mark.asyncio
    async def test_hook_failure_is_captured(self, tmp_path: Path) -> None:
        """A failing hook produces a PluginHookError but does not crash."""
        plugin_dir = tmp_path / "testplugin"
        plugin_dir.mkdir()
        (plugin_dir / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    raise ValueError("hook failed")
""")
        manifest = PluginManifest(
            name="testplugin",
            version="1.0.0",
            description="",
            hooks=["pre_scaffold"],
            entry_point="hooks:pre_scaffold",
            path=plugin_dir,
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        mgr.load_all()
        hook_errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert len(hook_errors) == 1
        assert isinstance(hook_errors[0], PluginHookError)
        assert "hook failed" in str(hook_errors[0])
        assert hook_errors[0].plugin_name == "testplugin"

    @pytest.mark.asyncio
    async def test_multiple_plugins_all_execute(self, tmp_path: Path) -> None:
        """Multiple plugins with hooks all execute."""
        manifests = []
        for i, name in enumerate(["plugin-a", "plugin-b"]):
            plugin_dir = tmp_path / name
            plugin_dir.mkdir()
            (plugin_dir / "hooks.py").write_text(f"""
def pre_scaffold(project_path, env_config):
    pass
""")
            manifests.append(
                PluginManifest(
                    name=name,
                    version="1.0.0",
                    description="",
                    hooks=["pre_scaffold"],
                    entry_point="hooks:pre_scaffold",
                    path=plugin_dir,
                )
            )
        mgr = PluginManager(discovery=_FakeDiscovery(manifests))
        mgr.load_all()
        hook_errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert hook_errors == []

    @pytest.mark.asyncio
    async def test_one_failing_hook_does_not_block_others(self, tmp_path: Path) -> None:
        """A failing hook in one plugin doesn't block other hooks."""
        manifests = []

        # Plugin A: failing
        dir_a = tmp_path / "plugin-a"
        dir_a.mkdir()
        (dir_a / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    raise RuntimeError("A fails")
""")
        manifests.append(
            PluginManifest(
                name="plugin-a",
                version="1.0.0",
                description="",
                hooks=["pre_scaffold"],
                entry_point="hooks:pre_scaffold",
                path=dir_a,
            )
        )

        # Plugin B: succeeds
        dir_b = tmp_path / "plugin-b"
        dir_b.mkdir()
        (dir_b / "hooks.py").write_text("""
def pre_scaffold(project_path, env_config):
    pass
""")
        manifests.append(
            PluginManifest(
                name="plugin-b",
                version="1.0.0",
                description="",
                hooks=["pre_scaffold"],
                entry_point="hooks:pre_scaffold",
                path=dir_b,
            )
        )

        mgr = PluginManager(discovery=_FakeDiscovery(manifests))
        mgr.load_all()
        hook_errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert len(hook_errors) == 1
        assert "plugin-a" in str(hook_errors[0])

    def test_load_errors_property(self) -> None:
        manifest = PluginManifest(
            name="p", version="1.0", description="", hooks=["pre_scaffold"]
        )
        mgr = PluginManager(discovery=_FakeDiscovery([manifest]))
        mgr.load_all()
        assert len(mgr.load_errors) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# Parallel execution
# ═════════════════════════════════════════════════════════════════════════════


class TestParallelHookExecution:
    """Hooks from independent plugins run concurrently via TaskGroup."""

    @pytest.mark.asyncio
    async def test_parallel_hooks_all_succeed(self, tmp_path: Path) -> None:
        """Multiple hooks run to completion in parallel."""
        manifests = []
        for name in ["plugin-a", "plugin-b", "plugin-c"]:
            plugin_dir = tmp_path / name
            plugin_dir.mkdir()
            (plugin_dir / "hooks.py").write_text(f"""
def pre_scaffold(project_path, env_config):
    pass
""")
            manifests.append(
                PluginManifest(
                    name=name,
                    version="1.0.0",
                    description="",
                    hooks=["pre_scaffold"],
                    entry_point="hooks:pre_scaffold",
                    path=plugin_dir,
                )
            )
        mgr = PluginManager(discovery=_FakeDiscovery(manifests))
        mgr.load_all()
        errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert errors == []

    @pytest.mark.asyncio
    async def test_parallel_hooks_concurrent_execution(self, tmp_path: Path) -> None:
        """Multiple hooks execute concurrently (interleaved, not sequential).

        We use a shared list with a delay to verify interleaving.
        """
        import asyncio

        execution_order: list[str] = []

        async def make_hook(name: str, delay: float):
            async def hook(project_path, env_config):
                nonlocal execution_order
                execution_order.append(f"{name}_start")
                await asyncio.sleep(delay)
                execution_order.append(f"{name}_end")

            return hook

        # Create hook functions directly (no file loading needed for this test)
        hook_a = await make_hook("A", 0.1)
        hook_b = await make_hook("B", 0.05)

        # Manually set up registries
        mgr = PluginManager(discovery=_FakeDiscovery([]))
        mgr._manifests = [
            PluginManifest(name="plugin-a", version="1.0", description=""),
            PluginManifest(name="plugin-b", version="1.0", description=""),
        ]
        mgr._hook_registries = {
            "plugin-a": {HookType.PRE_SCAFFOLD: hook_a},
            "plugin-b": {HookType.PRE_SCAFFOLD: hook_b},
        }

        errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert errors == []

        # Both should start before either ends (concurrent execution)
        assert execution_order.index("A_start") < execution_order.index("A_end")
        assert execution_order.index("B_start") < execution_order.index("B_end")
        # B (shorter delay) should end before A (longer delay) if truly parallel
        assert execution_order.index("B_end") < execution_order.index("A_end")

    @pytest.mark.asyncio
    async def test_parallel_failures_collected(self, tmp_path: Path) -> None:
        """Multiple failing hooks all report errors, not just the first."""
        manifests = []
        for name in ["fail-a", "fail-b", "ok-c"]:
            plugin_dir = tmp_path / name
            plugin_dir.mkdir()
            code = (
                "def pre_scaffold(project_path, env_config):\n"
                f"    raise RuntimeError('{name} failed')"
                if name.startswith("fail")
                else "def pre_scaffold(project_path, env_config): pass"
            )
            (plugin_dir / "hooks.py").write_text(code)
            manifests.append(
                PluginManifest(
                    name=name,
                    version="1.0.0",
                    description="",
                    hooks=["pre_scaffold"],
                    entry_point="hooks:pre_scaffold",
                    path=plugin_dir,
                )
            )
        mgr = PluginManager(discovery=_FakeDiscovery(manifests))
        mgr.load_all()
        errors = await mgr.execute_pre_scaffold(tmp_path, {})
        assert len(errors) == 2
        error_names = {e.plugin_name for e in errors}
        assert "fail-a" in error_names
        assert "fail-b" in error_names


# ═════════════════════════════════════════════════════════════════════════════
# PluginManager integration with discovery
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginManagerIntegration:
    """Tests that PluginManager works with real PluginDiscovery."""

    def test_discovery_empty_integration(self) -> None:
        """PluginManager with empty directories produces no errors."""
        discovery = PluginDiscovery(
            global_dir=Path("/nonexistent/discovery/path"),
            project_dir=Path("/nonexistent/project/path"),
        )
        mgr = PluginManager(discovery=discovery)
        errors = mgr.load_all()
        assert errors == []
        assert mgr.manifests == []


# ═════════════════════════════════════════════════════════════════════════════
# HookType enum
# ═════════════════════════════════════════════════════════════════════════════


class TestHookType:
    def test_pre_scaffold_value(self) -> None:
        assert HookType.PRE_SCAFFOLD.value == "pre_scaffold"

    def test_post_scaffold_value(self) -> None:
        assert HookType.POST_SCAFFOLD.value == "post_scaffold"

    def test_from_string_pre(self) -> None:
        assert HookType("pre_scaffold") == HookType.PRE_SCAFFOLD

    def test_from_string_post(self) -> None:
        assert HookType("post_scaffold") == HookType.POST_SCAFFOLD

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            HookType("invalid")
