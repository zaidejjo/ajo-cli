"""Abstract base class for architecture presets.

Every preset plugin (monolith, REST API, GraphQL, Docker) inherits from
:class:`AbstractPreset` and must implement the abstract methods defined
here.  Presets are pluggable via the registry in ``ajo/presets/__init__``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AbstractPreset(ABC):
    """Architecture preset plugin base.

    Subclasses define the *what* (dependencies, files to generate) and
    the *how* (the :meth:`scaffold` coroutine) for a particular project
    architecture template.

    Usage::

        class MyPreset(AbstractPreset):
            @property
            def name(self) -> str:
                return "My Architecture"

            @property
            def description(self) -> str:
                return "Custom architecture with extra batteries"

            @property
            def dependencies(self) -> list[str]:
                return ["django", "my-extra-lib"]

            @property
            def dev_dependencies(self) -> list[str]:
                return ["ruff", "mypy"]

            async def scaffold(self, project_path: Path,
                               env_config: dict[str, Any]) -> None:
                # Generate preset-specific files here
                ...
    """

    # ── Abstract properties ─────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name (e.g. ``"REST API Ready"``)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Single-line explanation of what this preset configures."""
        ...

    @property
    @abstractmethod
    def dependencies(self) -> list[str]:
        """PyPI package names required by this architecture.

        These packages will be installed with ``uv add`` during
        scaffolding.  Django itself should be included here.
        """
        ...

    @property
    @abstractmethod
    def dev_dependencies(self) -> list[str]:
        """PyPI package names for development only (e.g. linters).

        These packages will be installed with ``uv add --dev``.
        """
        ...

    # ── Abstract methods ─────────────────────────────────────────────────

    @property
    def preview_files(self) -> list[tuple[str, int]]:
        """Optional list of ``(relative_path, byte_size)`` tuples describing
        files that will be created by this preset.

        Used by :class:`~ajo.ui.theme.FileTreePreview` to render a live
        structural blueprint before scaffolding begins.

        The base implementation returns an empty list.  Subclasses that
        generate known files should override this to return a faithful
        representation of the output they produce.

        Returns:
            List of ``(path, size)`` tuples, where *path* is relative to
            the project root.  Directories have size ``0``.
        """
        return []

    @abstractmethod
    async def scaffold(
        self,
        project_path: Path,
        env_config: dict[str, Any],
    ) -> None:
        """Execute preset-specific scaffolding steps.

        This method is called **after** the :class:`ScaffoldEngine
        <ajo.scaffolding.engine.ScaffoldEngine>` has created the basic
        project directory, ``.env``, ``.gitignore``, and initialised
        ``git`` and ``uv``.  Implementations should:

        * Create the Django project structure (``manage.py``, settings,
          URLs, etc.).
        * Generate any additional files required by the architecture.
        * Modify generated files (e.g. injecting app registrations or
          middleware in ``settings.py``).

        The *env_config* dictionary contains:

        * ``project_name`` — name of the Django project.
        * ``db_type`` — ``"sqlite"``, ``"postgresql"``, or ``"mysql"``.
        * ``db_config`` — database connection parameters.
        * ``secret_key`` — a generated Django ``SECRET_KEY``.
        * ``preset_key`` — the registry key of this preset.

        Args:
            project_path: Root directory for the new Django project.
            env_config: Project-wide configuration dictionary.

        Raises:
            PresetError: If any step of the preset scaffolding fails.
        """
        ...

    # ── Concrete helpers ─────────────────────────────────────────────────

    @classmethod
    def registry_key(cls) -> str:
        """Return the key used to register this preset in :data:`PRESET_REGISTRY`.

        By default the key is the lower-cased, space-to-hyphen converted
        class name without the ``"Preset"`` suffix (e.g. ``"RestAPI"`` →
        ``"rest-api"``).  Subclasses may override this for custom keys.
        """
        name = cls.__name__
        if name.endswith("Preset"):
            name = name[: -len("Preset")]
        # Insert hyphens before uppercase letters, then lower
        result = ""
        for char in name:
            if char.isupper() and result:
                result += "-"
            result += char.lower()
        return result

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self.name!r}>"
