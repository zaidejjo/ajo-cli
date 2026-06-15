"""Pluggable architecture preset system.

Every concrete :class:`~ajo.presets.base.AbstractPreset` subclass is
registered in :data:`PRESET_REGISTRY` and can be looked up by its
:meth:`~ajo.presets.base.AbstractPreset.registry_key`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ajo.presets.base import AbstractPreset

# ── Lazy registry -----------------------------------------------------------
# Registrations happen at the bottom of this module after the preset
# classes have been imported.

PRESET_REGISTRY: dict[str, type[AbstractPreset]] = {}
"""Mapping of preset keys (e.g. ``"monolith"``, ``"rest-api"``) to their
concrete :class:`AbstractPreset` subclasses.

Populated by :func:`register` calls at module import time.
"""


def register(preset_cls: type[AbstractPreset]) -> type[AbstractPreset]:
    """Decorator / direct-call to register a preset class.

    Usage::

        @register
        class MyPreset(AbstractPreset):
            ...

    Or equivalently::

        register(MyPreset)
    """
    key = preset_cls.registry_key()
    if key in PRESET_REGISTRY:
        from ajo.core.exceptions import PresetError

        raise PresetError(
            f"A preset with key {key!r} is already registered "
            f"({PRESET_REGISTRY[key].__name__})."
        )
    PRESET_REGISTRY[key] = preset_cls
    return preset_cls


def get_preset(key: str) -> type[AbstractPreset]:
    """Look up a preset class by its registry key.

    Args:
        key: Registry key (e.g. ``"rest-api"``).

    Returns:
        The matching preset class.

    Raises:
        PresetError: If *key* is not found in the registry.
    """
    try:
        return PRESET_REGISTRY[key]
    except KeyError:
        from ajo.core.exceptions import PresetError

        available = ", ".join(sorted(PRESET_REGISTRY))
        raise PresetError(f"Unknown preset {key!r}. Available: {available}") from None


def list_presets() -> list[tuple[str, str]]:
    """Return a list of ``(key, name)`` tuples for every registered preset.

    Useful for populating interactive menus.
    """
    return [(key, cls.name) for key, cls in sorted(PRESET_REGISTRY.items())]


# ── Import preset implementations so they register themselves ───────────────

from ajo.presets.monolith import MonolithPreset  # noqa: E402, F811
from ajo.presets.rest_api import RestAPIPreset  # noqa: E402, F811
from ajo.presets.graphql_api import GraphQLPreset  # noqa: E402, F811
from ajo.presets.docker import DockerPreset  # noqa: E402, F811

__all__ = [
    "PRESET_REGISTRY",
    "register",
    "get_preset",
    "list_presets",
    "AbstractPreset",
]
# Re-export for convenience
from ajo.presets.base import AbstractPreset  # noqa: E402, F401
