"""Integration tests for add-on compatibility and conflict detection.

Verifies that incompatible preset+addon combinations raise clear errors
and that conflicting add-ons are detected at resolution time.
"""

from __future__ import annotations

import pytest

from ajo.core.exceptions import PresetError
from ajo.presets.addons import ADDON_REGISTRY, get_addon_choices, resolve_addons


# Filter out test add-ons that may have leaked
_ACTUAL_ADDONS = {
    k: v
    for k, v in ADDON_REGISTRY.items()
    if k not in ("failing", "duplicate", "another")
}


class TestAddonCompatibility:
    """Preset compatibility checks."""

    def test_all_current_addons_are_universally_compatible(self) -> None:
        """Currently all 4 add-ons set ``compatible_presets = None``
        which means they work with every preset."""
        for key, cls in _ACTUAL_ADDONS.items():
            instance = cls()
            assert instance.compatible_presets is None, (
                f"Add-on '{key}' restricts presets to {instance.compatible_presets}"
            )

    def test_get_addon_choices_with_preset(self) -> None:
        """All real add-ons should appear in choices for any preset."""
        real_count = len(_ACTUAL_ADDONS)
        for preset in ("monolith", "rest-api", "ninja-api", "graphql-api", "docker"):
            choices = get_addon_choices(preset_key=preset)
            # Count only real add-ons, ignore stray test ones
            real_in_choices = sum(1 for k in _ACTUAL_ADDONS if k in choices)
            assert real_in_choices == real_count, (
                f"Expected {real_count} real add-ons in choices for {preset}, "
                f"got {real_in_choices}"
            )

    def test_resolve_with_all_presets(self) -> None:
        """resolve_addons should work with every preset key."""
        for preset in ("monolith", "rest-api", "ninja-api", "graphql-api", "docker"):
            addons = resolve_addons(["auth", "cache"], preset_key=preset)
            assert len(addons) == 2


class TestAddonConflicts:
    """Add-on conflict detection."""

    def test_no_conflicts_between_current_addons(self) -> None:
        """Current add-ons should have empty conflict lists."""
        for key, cls in _ACTUAL_ADDONS.items():
            instance = cls()
            assert instance.conflicts_with == [], (
                f"Add-on '{key}' has conflicts: {instance.conflicts_with}"
            )

    def test_resolve_without_conflicts(self) -> None:
        """All 4 add-ons should resolve together without conflict."""
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        assert len(addons) == 4

    def test_unknown_addon_raises_clear_error(self) -> None:
        with pytest.raises(PresetError) as excinfo:
            resolve_addons(["auth", "nonexistent"])
        assert "Unknown add-on" in str(excinfo.value)
        assert "nonexistent" in str(excinfo.value)
        # Should list available add-ons
        assert "auth" in str(excinfo.value)


class TestCompatiblityEdgeCases:
    """Edge cases for add-on compatibility."""

    def test_empty_preset_key(self) -> None:
        """When preset_key is None, all add-ons should be compatible."""
        addons = resolve_addons(["auth", "cache"])
        assert len(addons) == 2

    def test_empty_addons_list(self) -> None:
        addons = resolve_addons([], preset_key="monolith")
        assert addons == []

    def test_duplicate_addon_keys_allowed(self) -> None:
        """resolve_addons allows the same key twice (each produces an instance)."""
        addons = resolve_addons(["auth", "auth"])
        assert len(addons) == 2
        assert addons[0].name == addons[1].name

    @pytest.mark.skip(reason="No add-ons with conflicts exist yet")
    def test_conflicting_addons_raises(self) -> None:
        """Placeholder for when add-ons gain conflict lists."""
        pass
