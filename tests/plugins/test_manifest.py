"""Tests for ManifestValidator and PluginManifest data model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ajo.plugins.exceptions import PluginValidationError, PluginVersionError
from ajo.plugins.manifest import (
    ALL_HOOK_TYPES,
    ManifestValidator,
    REQUIRED_FIELDS,
    PluginManifest,
    _parse_version,
    _version_satisfies,
)


# ═════════════════════════════════════════════════════════════════════════════
# _parse_version
# ═════════════════════════════════════════════════════════════════════════════


class TestParseVersion:
    def test_three_part(self) -> None:
        assert _parse_version("3.2.1") == (3, 2, 1)

    def test_two_part(self) -> None:
        assert _parse_version("1.0") == (1, 0)

    def test_single_part(self) -> None:
        assert _parse_version("5") == (5,)

    def test_invalid_string(self) -> None:
        with pytest.raises(PluginValidationError, match="Invalid version format"):
            _parse_version("abc")

    def test_invalid_mixed(self) -> None:
        with pytest.raises(PluginValidationError, match="Invalid version format"):
            _parse_version("1.2.abc")


# ═════════════════════════════════════════════════════════════════════════════
# _version_satisfies
# ═════════════════════════════════════════════════════════════════════════════


class TestVersionSatisfies:
    def test_no_constraints(self) -> None:
        assert _version_satisfies("3.2.0") is True

    def test_min_version_exact(self) -> None:
        assert _version_satisfies("3.2.0", min_ver="3.2.0") is True

    def test_min_version_above(self) -> None:
        assert _version_satisfies("3.3.0", min_ver="3.2.0") is True

    def test_min_version_below(self) -> None:
        assert _version_satisfies("3.1.0", min_ver="3.2.0") is False

    def test_max_version_under(self) -> None:
        assert _version_satisfies("3.2.0", max_ver="4.0.0") is True

    def test_max_version_at_limit(self) -> None:
        assert _version_satisfies("4.0.0", max_ver="4.0.0") is False

    def test_max_version_above(self) -> None:
        assert _version_satisfies("4.1.0", max_ver="4.0.0") is False

    def test_range_within(self) -> None:
        assert _version_satisfies("3.5.0", min_ver="3.2.0", max_ver="4.0.0") is True

    def test_range_below(self) -> None:
        assert _version_satisfies("3.0.0", min_ver="3.2.0", max_ver="4.0.0") is False

    def test_range_above(self) -> None:
        assert _version_satisfies("4.0.0", min_ver="3.2.0", max_ver="4.0.0") is False


# ═════════════════════════════════════════════════════════════════════════════
# PluginManifest
# ═════════════════════════════════════════════════════════════════════════════


class TestPluginManifest:
    def test_minimal_manifest(self) -> None:
        m = PluginManifest(name="my-plugin", version="1.0.0")
        assert m.name == "my-plugin"
        assert m.version == "1.0.0"
        assert m.description == ""
        assert m.author is None

    def test_full_manifest(self) -> None:
        m = PluginManifest(
            name="my-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            min_ajo_version="3.0.0",
            max_ajo_version="4.0.0",
            hooks=["pre_scaffold"],
            entry_point="my_plugin.hooks",
            path=Path("/some/path"),
        )
        assert m.author == "Test Author"
        assert m.min_ajo_version == "3.0.0"
        assert m.hooks == ["pre_scaffold"]

    def test_is_frozen(self) -> None:
        m = PluginManifest(name="p", version="1.0.0")
        with pytest.raises(AttributeError):
            m.name = "other"  # type: ignore[misc]


# ═════════════════════════════════════════════════════════════════════════════
# ManifestValidator — loads (file-based)
# ═════════════════════════════════════════════════════════════════════════════


class TestManifestValidatorLoad:
    SAMPLE_MANIFEST = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "author": "Test Author",
        "min_ajo_version": "3.0.0",
    }

    @pytest.fixture
    def validator(self) -> ManifestValidator:
        return ManifestValidator()

    @pytest.fixture
    def plugin_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "my-plugin"
        d.mkdir(parents=True)
        return d

    def _write_manifest(self, plugin_dir: Path, data: dict) -> Path:
        path = plugin_dir / "addon.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    def test_valid_manifest(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(plugin_dir, self.SAMPLE_MANIFEST)
        manifest, errors = validator.load(plugin_dir)
        assert errors == []
        assert manifest is not None
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.author == "Test Author"
        assert manifest.path == plugin_dir.resolve()

    def test_missing_addon_json(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        manifest, errors = validator.load(plugin_dir)
        assert manifest is None
        assert len(errors) == 1
        assert "Missing addon.json" in str(errors[0])

    def test_malformed_json(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        (plugin_dir / "addon.json").write_text("not json {")
        manifest, errors = validator.load(plugin_dir)
        assert manifest is None
        assert len(errors) == 1
        assert "Invalid JSON" in str(errors[0])

    def test_missing_required_fields(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(plugin_dir, {"name": "test-plugin"})
        manifest, errors = validator.load(plugin_dir)
        assert manifest is None
        assert any("version" in str(e) for e in errors)
        assert any("description" in str(e) for e in errors)

    def test_wrong_field_type(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {"name": 123, "version": "1.0", "description": "desc"},
        )
        manifest, errors = validator.load(plugin_dir)
        assert manifest is None
        assert any("name" in str(e) and "str" in str(e) for e in errors)

    def test_version_compatibility_pass(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "desc",
                "min_ajo_version": "3.0.0",
                "max_ajo_version": "10.0.0",
            },
        )
        manifest, errors = validator.load(plugin_dir)
        assert errors == []
        assert manifest is not None

    def test_version_compatibility_fail(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "desc",
                "min_ajo_version": "99.0.0",
            },
        )
        manifest, errors = validator.load(plugin_dir)
        assert manifest is None
        assert len(errors) >= 1
        assert isinstance(errors[0], PluginVersionError)
        assert "requires ajo version" in str(errors[0])

    def test_hooks_are_sanitised(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "desc",
                "hooks": ["pre_scaffold", "invalid_hook", "post_scaffold"],
            },
        )
        manifest, errors = validator.load(plugin_dir)
        assert errors == []
        assert manifest is not None
        assert "pre_scaffold" in manifest.hooks
        assert "post_scaffold" in manifest.hooks
        assert "invalid_hook" not in manifest.hooks

    def test_hooks_not_a_list(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "desc",
                "hooks": "pre_scaffold",
            },
        )
        # hooks field has type list - so wrong type should be caught
        manifest, errors = validator.load(plugin_dir)
        # hooks validation error would prevent manifest creation
        assert manifest is None or manifest.hooks == []

    def test_invalid_version_format(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {"name": "test-plugin", "version": "abc", "description": "desc"},
        )
        manifest, errors = validator.load(plugin_dir)
        assert manifest is None
        assert any("version" in str(e) for e in errors)

    def test_optional_fields_preserved(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        self._write_manifest(
            plugin_dir,
            {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "desc",
                "author": "Me",
                "entry_point": "mypkg.hooks",
            },
        )
        manifest, errors = validator.load(plugin_dir)
        assert errors == []
        assert manifest is not None
        assert manifest.author == "Me"
        assert manifest.entry_point == "mypkg.hooks"

    def test_load_returns_none_on_permission_error(
        self, validator: ManifestValidator, plugin_dir: Path
    ) -> None:
        # Create the file but make it unreadable
        path = self._write_manifest(plugin_dir, self.SAMPLE_MANIFEST)
        path.chmod(0o000)
        manifest, errors = validator.load(plugin_dir)
        path.chmod(0o644)  # restore for cleanup
        assert manifest is None
        assert len(errors) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# ManifestValidator — loads (string-based)
# ═════════════════════════════════════════════════════════════════════════════


class TestManifestValidatorLoads:
    def test_valid_json_string(self) -> None:
        validator = ManifestValidator()
        raw = json.dumps(
            {
                "name": "string-plugin",
                "version": "2.0.0",
                "description": "From string",
            }
        )
        manifest, errors = validator.loads(raw)
        assert errors == []
        assert manifest is not None
        assert manifest.name == "string-plugin"

    def test_invalid_json_string(self) -> None:
        validator = ManifestValidator()
        manifest, errors = validator.loads("not json")
        assert manifest is None
        assert len(errors) == 1

    def test_with_source_path(self) -> None:
        validator = ManifestValidator()
        raw = json.dumps({"name": "p", "version": "1.0", "description": "d"})
        manifest, errors = validator.loads(raw, source_path="test/path")
        assert errors == []
        assert manifest is not None
        assert manifest.name == "p"


# ═════════════════════════════════════════════════════════════════════════════
# Schema constants
# ═════════════════════════════════════════════════════════════════════════════


class TestSchemaConstants:
    def test_required_fields_contain_name(self) -> None:
        assert "name" in REQUIRED_FIELDS

    def test_required_fields_contain_version(self) -> None:
        assert "version" in REQUIRED_FIELDS

    def test_required_fields_contain_description(self) -> None:
        assert "description" in REQUIRED_FIELDS

    def test_all_hook_types(self) -> None:
        assert "pre_scaffold" in ALL_HOOK_TYPES
        assert "post_scaffold" in ALL_HOOK_TYPES
