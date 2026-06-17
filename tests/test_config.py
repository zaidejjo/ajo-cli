"""Tests for ``ajo.core.config.ConfigManager``.

All tests use ``tmp_path`` + ``monkeypatch`` to redirect ``CONFIG_DIR``
and ``CONFIG_FILE`` so that no real ``~/.config/ajo`` is ever touched.
Permission errors are simulated by monkeypatching ``Path.write_text`` /
``Path.read_text`` — no ``chmod`` is used, ensuring portability across
Windows, Linux, and CI environments.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def config_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a temp directory that stands in for ``~/.config/ajo``."""
    return tmp_path / ".config" / "ajo"


@pytest.fixture
def cfg_module(config_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Return the ``ajo.core.config`` module with paths redirected to *tmp_path*.

    Patches ``CONFIG_DIR`` and ``CONFIG_FILE`` *before* the
    :class:`ConfigManager` is instantiated so the manager reads/writes
    exclusively inside the temp directory.
    """
    import ajo.core.config as m

    monkeypatch.setattr(m, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(m, "CONFIG_FILE", config_dir / "config.json")
    return m


@pytest.fixture
def config_manager(cfg_module):
    """Return a fresh :class:`ConfigManager` pointed at the temp directory.

    Cleans up the global reference after the test.
    """
    mgr = cfg_module.ConfigManager()
    yield mgr
    # Restore global so other tests start clean
    cfg_module._global_config = None


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestDefaults:
    """ConfigManager behaviour when no config file exists."""

    def test_defaults_on_missing_file(self, config_manager):
        """No file on disk → defaults, first_run=True, nerd_fonts is None."""
        assert config_manager.is_first_run() is True
        assert config_manager.get("nerd_fonts") is None
        assert config_manager.get("nerd_fonts", default=False) is False
        assert config_manager.get("version") == 1

    def test_defaults_do_not_create_file(self, cfg_module, config_manager):
        """Loading defaults does NOT write anything to disk."""
        assert not cfg_module.CONFIG_FILE.exists()

    def test_is_first_run_true_when_null(self, config_manager):
        """nerd_fonts: null → is_first_run() is True."""
        assert config_manager.is_first_run() is True


class TestReadWrite:
    """Reading and writing config.json."""

    def test_save_creates_file(self, cfg_module, config_manager):
        """.save() with dirty data creates config.json."""
        config_manager.set("nerd_fonts", True)
        assert not cfg_module.CONFIG_FILE.exists()  # not saved yet
        config_manager.save()
        assert cfg_module.CONFIG_FILE.is_file()

    def test_save_creates_directory(self, cfg_module, config_manager):
        """.save() creates the ~/.config/ajo directory."""
        config_manager.set("nerd_fonts", True, auto_save=True)
        assert cfg_module.CONFIG_DIR.is_dir()

    def test_save_writes_correct_content(self, cfg_module, config_manager):
        """Saved JSON has expected keys."""
        config_manager.set("nerd_fonts", False, auto_save=True)
        raw = cfg_module.CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["nerd_fonts"] is False
        assert data["version"] == 1
        assert "updated_at" in data

    def test_reads_saved_file(self, cfg_module, config_manager):
        """Fresh ConfigManager reads previously saved values."""
        config_manager.set("nerd_fonts", True, auto_save=True)
        # Create a second manager to simulate a new process
        cfg_module._global_config = None
        mgr2 = cfg_module.ConfigManager()
        assert mgr2.is_first_run() is False
        assert mgr2.get("nerd_fonts") is True

    def test_is_first_run_false_after_set(self, config_manager):
        """After nerd_fonts is set to any boolean, is_first_run is False."""
        config_manager.set("nerd_fonts", True)
        assert config_manager.is_first_run() is False
        config_manager.set("nerd_fonts", False)
        assert config_manager.is_first_run() is False


class TestDirtyTracking:
    """Internal dirty flag and no-op save."""

    def test_dirty_after_set(self, config_manager):
        """.set() marks the instance as dirty."""
        assert config_manager._dirty is False
        config_manager.set("nerd_fonts", True)
        assert config_manager._dirty is True

    def test_save_clears_dirty(self, config_manager):
        """.save() clears the dirty flag."""
        config_manager.set("nerd_fonts", True)
        config_manager.save()
        assert config_manager._dirty is False

    def test_noop_save_does_not_write(self, cfg_module, config_manager):
        """Calling .save() without dirty → no file written."""
        config_manager.save()
        assert not cfg_module.CONFIG_FILE.exists()


class TestMergeDefaults:
    """Merging defaults when loading partial configs."""

    def test_merge_with_defaults(self, cfg_module, config_manager):
        """File with only 'nerd_fonts' → defaults fill missing keys."""
        # Write partial JSON by hand
        cfg_module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg_module.CONFIG_FILE.write_text(
            json.dumps({"nerd_fonts": True}), encoding="utf-8"
        )
        cfg_module._global_config = None
        mgr2 = cfg_module.ConfigManager()
        assert mgr2.get("nerd_fonts") is True
        assert mgr2.get("version") == 1  # from defaults

    def test_updated_at_timestamped(self, config_manager):
        """.set() stamps an ISO‑8601 timestamp."""
        config_manager.set("nerd_fonts", True)
        ts = config_manager._data.get("updated_at")
        assert ts is not None
        # Verify it's valid ISO‑8601 by parsing it
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None  # timezone-aware


class TestEdgeCases:
    """Corrupt files, missing directories, permission errors."""

    def test_corrupt_json_falls_back_to_defaults(self, cfg_module):
        """Unparseable JSON → silently use defaults, no crash."""
        cfg_module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg_module.CONFIG_FILE.write_text("{broken", encoding="utf-8")
        cfg_module._global_config = None
        mgr = cfg_module.ConfigManager()
        assert mgr.get("nerd_fonts") is None
        assert mgr.is_first_run() is True

    def test_permission_error_read(self, cfg_module, monkeypatch):
        """File exists but can't be read → fall back to defaults."""
        # Create a valid file first
        cfg_module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg_module.CONFIG_FILE.write_text(
            json.dumps({"nerd_fonts": True}), encoding="utf-8"
        )

        original_read = pathlib.Path.read_text

        def mock_read(self, *args, **kwargs):
            if "config.json" in str(self):
                raise PermissionError("Permission denied")
            return original_read(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
        cfg_module._global_config = None
        mgr = cfg_module.ConfigManager()
        # Falls back to defaults
        assert mgr.get("nerd_fonts") is None
        assert mgr.is_first_run() is True

    def test_permission_error_write(self, cfg_module, monkeypatch):
        """Cannot write to config → save fails silently, no crash."""
        cfg_module.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        original_write = pathlib.Path.write_text

        def mock_write(self, *args, **kwargs):
            if "config.json" in str(self):
                raise PermissionError("Permission denied")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "write_text", mock_write)
        cfg_module._global_config = None
        mgr = cfg_module.ConfigManager()
        mgr.set("nerd_fonts", True)
        mgr.save()  # Should not raise
        # File should NOT have been written
        assert not cfg_module.CONFIG_FILE.exists()

    def test_oserror_on_write(self, cfg_module, monkeypatch):
        """Read-only filesystem → save fails silently, no crash."""
        original_write = pathlib.Path.write_text

        def mock_write(self, *args, **kwargs):
            if "config.json" in str(self):
                raise OSError("Read-only file system")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "write_text", mock_write)
        cfg_module._global_config = None
        mgr = cfg_module.ConfigManager()
        mgr.set("nerd_fonts", False, auto_save=True)
        # No exception — graceful degradation
        assert mgr.get("nerd_fonts") is False


class TestGlobalReference:
    """_global_config and get_config() contract."""

    def test_global_config_set_on_init(self, cfg_module):
        """After ConfigManager() init, _global_config is the instance."""
        cfg_module._global_config = None
        mgr = cfg_module.ConfigManager()
        assert cfg_module._global_config is mgr

    def test_get_config_returns_instance(self, cfg_module):
        """get_config() returns the same instance set by ConfigManager()."""
        cfg_module._global_config = None
        mgr = cfg_module.ConfigManager()
        assert cfg_module.get_config() is mgr

    def test_get_config_before_init(self, cfg_module):
        """get_config() returns None before any ConfigManager is created."""
        cfg_module._global_config = None
        assert cfg_module.get_config() is None

    def test_repr(self, config_manager):
        """__repr__ includes the nerd_fonts value."""
        config_manager.set("nerd_fonts", True)
        r = repr(config_manager)
        assert "nerd_fonts=True" in r
