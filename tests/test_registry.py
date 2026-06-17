"""Unit tests for the add-on registry (``ADDON_REGISTRY``, ``get_addon()``,
``resolve_addons()``, ``get_addon_choices()``).
"""

from __future__ import annotations

import pytest

from ajo.core.exceptions import PresetError
from ajo.presets.addons import (
    ADDON_REGISTRY,
    AbstractAddon,
    get_addon,
    get_addon_choices,
    register_addon,
    resolve_addons,
)


_KNOWN_ADDONS = {"auth", "cache", "security", "testing"}


@pytest.fixture(autouse=True)
def _cleanup_stray_addons():
    """Remove any add-ons that leaked from other test files."""
    yield
    for key in list(ADDON_REGISTRY):
        if key not in _KNOWN_ADDONS:
            ADDON_REGISTRY.pop(key, None)


# Re-export for other tests in this module
cleanup_stray_addons = _cleanup_stray_addons


class TestRegistry:
    """``ADDON_REGISTRY`` and ``register_addon()``."""

    def test_all_addons_registered(self, registered_addon_keys: list[str]) -> None:
        # Filter out any stray test add-ons
        actual = {
            k for k in ADDON_REGISTRY if k not in ("failing", "duplicate", "another")
        }
        assert actual == set(registered_addon_keys)

    def test_registry_values_are_abstract_addon_subclasses(self) -> None:
        for cls in ADDON_REGISTRY.values():
            assert issubclass(cls, AbstractAddon)

    def test_registry_values_have_metadata(self) -> None:
        for key, cls in ADDON_REGISTRY.items():
            instance = cls()
            assert instance.name, f"{key} has empty name"
            assert instance.description, f"{key} has empty description"
            assert isinstance(instance.dependencies, list)

    def test_register_addon_duplicate_raises(self) -> None:
        """Registering when the key already exists should raise PresetError."""

        # A dummy add-on to occupy the "duplicate" slot
        class OccupyingAddon(AbstractAddon):
            name = "Occupying"
            description = "Already in the registry"

            async def apply(self, *args, **kwargs):
                pass

        ADDON_REGISTRY["duplicate"] = OccupyingAddon

        # ``DuplicateAddon.__name__`` → ``_derive_key`` → ``"duplicate"`` → collision!
        class DuplicateAddon(AbstractAddon):
            name = "Duplicate"
            description = "Testing"

            async def apply(self, *args, **kwargs):
                pass

        with pytest.raises(PresetError, match="already registered"):
            register_addon(DuplicateAddon)

        # Clean up
        ADDON_REGISTRY.pop("duplicate", None)

    def test_register_addon_is_idempotent_for_same_class(self) -> None:
        """register_addon should raise if called twice on any class."""

        # Use a unique dynamically defined class
        class AnotherAddon(AbstractAddon):
            name = "Another"
            description = "Testing idempotency"

            async def apply(self, *args, **kwargs):
                pass

        register_addon(AnotherAddon)
        with pytest.raises(PresetError):
            register_addon(AnotherAddon)

        # Clean up registry to not affect other tests
        ADDON_REGISTRY.pop("another", None)


class TestGetAddon:
    """``get_addon()``"""

    def test_get_existing_addon(self) -> None:
        cls = get_addon("auth")
        assert cls.__name__ == "AuthAddon"

    def test_get_nonexistent_addon_raises(self) -> None:
        with pytest.raises(PresetError, match="Unknown add-on"):
            get_addon("nonexistent")


class TestResolveAddons:
    """``resolve_addons()``"""

    def test_resolve_single_addon(self) -> None:
        addons = resolve_addons(["auth"])
        assert len(addons) == 1
        assert addons[0].name == "Auth & Users"

    def test_resolve_multiple_addons(self) -> None:
        addons = resolve_addons(["auth", "cache", "security"])
        assert len(addons) == 3

    def test_resolve_unknown_addon_raises(self) -> None:
        with pytest.raises(PresetError, match="Unknown add-on"):
            resolve_addons(["auth", "does_not_exist"])

    def test_resolve_all_addons(self) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        assert len(addons) == 4

    def test_resolve_with_preset_filter(self) -> None:
        # All current addons are compatible with all presets, so this should work
        addons = resolve_addons(["auth"], preset_key="ninja-api")
        assert len(addons) == 1


class TestGetAddonChoices:
    """``get_addon_choices()``"""

    def test_get_choices_contains_all(self, registered_addon_keys: list[str]) -> None:
        choices = get_addon_choices()
        assert set(choices.keys()) == set(registered_addon_keys)

    def test_choices_have_name_and_description(self) -> None:
        choices = get_addon_choices()
        for key, info in choices.items():
            assert "name" in info
            assert "description" in info
            assert info["name"]
            assert info["description"]

    def test_choices_filtered_by_preset(self) -> None:
        # When compatible_presets are set to a specific list, incompatible
        # choices should be hidden. Currently all are compatible everywhere.
        choices = get_addon_choices(preset_key="ninja-api")
        assert len(choices) == 4  # All compatible for now
