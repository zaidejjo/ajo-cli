"""Integration test: headless command-line add-on parsing and resolution.

Verifies that ``--addons`` and ``--no-addons`` flags are parsed correctly
and that the resolution logic works for headless execution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ajo.presets.addons import resolve_addons, get_addon_choices


class TestHeadlessAddonParsing:
    """Simulates the headless ``--addons`` CLI flag parsing logic."""

    def test_parse_single_addon(self) -> None:
        addons = resolve_addons(["auth"])
        assert len(addons) == 1
        assert addons[0].name == "Auth & Users"

    def test_parse_multiple_addons(self) -> None:
        addons = resolve_addons(["auth", "cache", "security", "testing"])
        assert len(addons) == 4

    def test_parse_with_preset_compatibility(self) -> None:
        addons = resolve_addons(["auth", "testing"], preset_key="rest-api")
        assert len(addons) == 2

    def test_parse_comma_separated_equivalent(self) -> None:
        """The CLI uses nargs='*', so each addon is a separate arg.
        Simulate what argparse passes: ['auth', 'cache']"""
        args = ["auth", "cache"]
        addons = resolve_addons(args)
        assert len(addons) == 2

    def test_empty_addons_list(self) -> None:
        addons = resolve_addons([])
        assert addons == []

    def test_unknown_addon_raises(self) -> None:
        with pytest.raises(Exception, match="Unknown add-on"):
            resolve_addons(["auth", "imaginary_addon"])

    def test_all_addon_choices_available(self) -> None:
        choices = get_addon_choices()
        assert "auth" in choices
        assert "cache" in choices
        assert "security" in choices
        assert "testing" in choices

    def test_headless_flow_simulation(self) -> None:
        """Simulate the complete headless resolution flow."""
        args_addons = ["auth", "cache"]
        preset_key = "monolith"

        if args_addons:
            addons = resolve_addons(args_addons, preset_key=preset_key)
            assert len(addons) == 2
            assert all(a.name for a in addons)
        else:
            pytest.fail("Addons should be resolved")
