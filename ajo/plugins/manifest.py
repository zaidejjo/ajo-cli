"""Plugin manifest data model and validation.

Every external plugin is defined by an ``addon.json`` manifest file in its
root directory.  The :class:`ManifestValidator` reads, parses, and validates
these manifests, producing a :class:`PluginManifest` dataclass on success.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ajo import __version__ as _ajo_version
from ajo.plugins.exceptions import PluginValidationError, PluginVersionError

# ── Schema ─────────────────────────────────────────────────────────────────────

REQUIRED_FIELDS: dict[str, type] = {
    "name": str,
    "version": str,
    "description": str,
}

OPTIONAL_FIELDS: dict[str, type] = {
    "author": str,
    "min_ajo_version": str,
    "max_ajo_version": str,
    "hooks": list,
    "entry_point": str,
}

ALL_HOOK_TYPES: set[str] = {"pre_scaffold", "post_scaffold"}
"""Standard hook types that a plugin may advertise."""


# ── Simple version comparison (supports X.Y.Z and X.Y) ─────────────────────━━


def _parse_version(ver: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable tuple of ints.

    ``"3.2.1"`` → ``(3, 2, 1)``

    Raises :exc:`PluginValidationError` if the string is not valid.
    """
    parts = ver.strip().split(".")
    if not parts or not all(p.isdigit() for p in parts):
        raise PluginValidationError(
            f'Invalid version format: {ver!r}. Expected dotted numbers (e.g. "3.2.0").'
        )
    return tuple(int(p) for p in parts)


def _version_satisfies(
    ajo_version: str,
    *,
    min_ver: str | None = None,
    max_ver: str | None = None,
) -> bool:
    """Check whether *ajo_version* falls within the ``[min, max)`` range.

    *min_ver* is inclusive, *max_ver* is exclusive (semver-style).
    If both are ``None``, all versions are accepted.
    """
    ajo_parts = _parse_version(ajo_version)

    if min_ver is not None:
        min_parts = _parse_version(min_ver)
        if ajo_parts < min_parts:
            return False

    if max_ver is not None:
        max_parts = _parse_version(max_ver)
        if ajo_parts >= max_parts:
            return False

    return True


# ── Manifest data model ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class PluginManifest:
    """Validated content of an ``addon.json`` plugin manifest.

    Attributes:
        name: Machine-readable plugin identifier (snake_case).
        version: Plugin version (``X.Y.Z``).
        description: Human-readable one-line summary.
        author: Optional author name.
        min_ajo_version: Minimum compatible ajo version (inclusive).
        max_ajo_version: Maximum compatible ajo version (exclusive).
        hooks: List of hook types the plugin implements.
        entry_point: Python dotted import path to the hook callable module.
        path: Absolute filesystem path to the plugin directory.
    """

    name: str
    version: str
    description: str = ""
    author: str | None = None
    min_ajo_version: str | None = None
    max_ajo_version: str | None = None
    hooks: list[str] = field(default_factory=list)
    entry_point: str | None = None
    path: Path | None = None


# ── Validator ─────────────────────────────────────────────────────────────────


_MANIFEST_FILENAME = "addon.json"


class ManifestValidator:
    """Reads, validates, and parses ``addon.json`` plugin manifests.

    Usage::

        validator = ManifestValidator()
        manifest, errors = validator.load(plugin_dir)
        if errors:
            for err in errors:
                ...
        else:
            print(manifest.name)
    """

    # ── Public API ───────────────────────────────────────────────────────

    def load(
        self,
        plugin_dir: Path,
    ) -> tuple[PluginManifest | None, list[PluginValidationError]]:
        """Load and validate a plugin manifest from a directory.

        Args:
            plugin_dir: Directory that should contain ``addon.json``.

        Returns:
            A ``(manifest, errors)`` pair.  If validation passes,
            *manifest* is a :class:`PluginManifest` and *errors* is empty.
            If validation fails, *manifest* is ``None`` and *errors*
            contains one or more :class:`PluginValidationError` instances.
        """
        errors: list[PluginValidationError] = []

        # ── File exists? ────────────────────────────────────────────────
        manifest_path = plugin_dir / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            errors.append(
                PluginValidationError(
                    f"Missing {_MANIFEST_FILENAME} in {plugin_dir}",
                    path=str(plugin_dir),
                )
            )
            return None, errors

        # ── Parse JSON ──────────────────────────────────────────────────
        try:
            raw = manifest_path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(
                PluginValidationError(
                    f"Invalid JSON in {manifest_path}: {exc}",
                    path=str(manifest_path),
                )
            )
            return None, errors
        except (OSError, PermissionError) as exc:
            errors.append(
                PluginValidationError(
                    f"Cannot read {manifest_path}: {exc}",
                    path=str(manifest_path),
                )
            )
            return None, errors

        # ── Schema validation ───────────────────────────────────────────
        schema_errors = self._validate_schema(data, str(manifest_path))
        errors.extend(schema_errors)
        if schema_errors:
            return None, errors

        # ── Version compatibility ────────────────────────────────────────
        ver_errors = self._validate_version_compatibility(data, str(manifest_path))
        errors.extend(ver_errors)
        if ver_errors:
            return None, errors

        # ── Build manifest ───────────────────────────────────────────────
        manifest = PluginManifest(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data.get("description", "")),
            author=str(data["author"]) if "author" in data else None,
            min_ajo_version=str(data.get("min_ajo_version") or None),
            max_ajo_version=str(data.get("max_ajo_version") or None),
            hooks=self._validate_hook_list(data.get("hooks", [])),
            entry_point=str(data["entry_point"]) if "entry_point" in data else None,
            path=plugin_dir.resolve(),
        )

        return manifest, errors

    def loads(
        self,
        raw: str,
        *,
        source_path: str | None = None,
    ) -> tuple[PluginManifest | None, list[PluginValidationError]]:
        """Load and validate a manifest from a raw JSON string.

        This is useful for tests and for manifests read from alternate
        sources (e.g. stdin or embedded resources).

        Args:
            raw: JSON string.
            source_path: Optional human-readable path label for error messages.

        Returns:
            Same as :meth:`load`.
        """
        errors: list[PluginValidationError] = []
        path_label = source_path or "<unknown>"

        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(
                PluginValidationError(
                    f"Invalid JSON: {exc}",
                    path=path_label,
                )
            )
            return None, errors

        schema_errors = self._validate_schema(data, path_label)
        errors.extend(schema_errors)
        if schema_errors:
            return None, errors

        ver_errors = self._validate_version_compatibility(data, path_label)
        errors.extend(ver_errors)
        if ver_errors:
            return None, errors

        manifest = PluginManifest(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data.get("description", "")),
            author=str(data["author"]) if "author" in data else None,
            min_ajo_version=str(data.get("min_ajo_version") or None),
            max_ajo_version=str(data.get("max_ajo_version") or None),
            hooks=self._validate_hook_list(data.get("hooks", [])),
            entry_point=str(data["entry_point"]) if "entry_point" in data else None,
        )

        return manifest, errors

    # ── Internal schema helpers ──────────────────────────────────────────

    @staticmethod
    def _validate_schema(
        data: dict[str, Any],
        path_label: str,
    ) -> list[PluginValidationError]:
        """Check required field presence and types."""
        errors: list[PluginValidationError] = []

        for field_name, field_type in REQUIRED_FIELDS.items():
            if field_name not in data:
                errors.append(
                    PluginValidationError(
                        f"Missing required field {field_name!r}",
                        path=path_label,
                        reasons=[f"Required field {field_name!r} is missing"],
                    )
                )
            elif not isinstance(data[field_name], field_type):
                errors.append(
                    PluginValidationError(
                        f"Field {field_name!r} must be of type "
                        f"{field_type.__name__}, got "
                        f"{type(data[field_name]).__name__}",
                        path=path_label,
                        reasons=[
                            f"Field {field_name!r} expected "
                            f"{field_type.__name__}, got "
                            f"{type(data[field_name]).__name__}"
                        ],
                    )
                )

        for field_name, field_type in OPTIONAL_FIELDS.items():
            if field_name in data and not isinstance(data[field_name], field_type):
                errors.append(
                    PluginValidationError(
                        f"Optional field {field_name!r} must be of type "
                        f"{field_type.__name__} if present, got "
                        f"{type(data[field_name]).__name__}",
                        path=path_label,
                        reasons=[
                            f"Field {field_name!r} expected "
                            f"{field_type.__name__}, got "
                            f"{type(data[field_name]).__name__}"
                        ],
                    )
                )

        # Validate version format
        for ver_field in ("version", "min_ajo_version", "max_ajo_version"):
            val = data.get(ver_field)
            if val is not None and not isinstance(val, str):
                continue  # type mismatch already reported above
            if val is not None:
                # Quick check: dotted numbers
                parts = val.strip().split(".")
                if not parts or not all(p.isdigit() for p in parts):
                    errors.append(
                        PluginValidationError(
                            f"Field {ver_field!r} value {val!r} is not a valid "
                            f'dotted version string (e.g. "3.2.0")',
                            path=path_label,
                            reasons=[
                                f"Field {ver_field!r} expected dotted version, "
                                f"got {val!r}"
                            ],
                        )
                    )

        return errors

    @staticmethod
    def _validate_version_compatibility(
        data: dict[str, Any],
        path_label: str,
    ) -> list[PluginValidationError]:
        """Check that the manifest's version range is compatible with the
        current ajo version."""
        errors: list[PluginValidationError] = []
        min_ver = data.get("min_ajo_version")
        max_ver = data.get("max_ajo_version")

        if min_ver is None and max_ver is None:
            return errors  # No constraints → always compatible

        try:
            compatible = _version_satisfies(
                _ajo_version,
                min_ver=min_ver,
                max_ver=max_ver,
            )
        except PluginValidationError as exc:
            errors.append(exc)
            return errors

        if not compatible:
            range_desc = ManifestValidator._format_version_range(min_ver, max_ver)
            errors.append(
                PluginVersionError(
                    f"Plugin requires ajo version {range_desc}, "
                    f"but current version is {_ajo_version}",
                    path=path_label,
                    reasons=[
                        f"Requires {range_desc}, current ajo version is {_ajo_version}"
                    ],
                )
            )

        return errors

    @staticmethod
    def _validate_hook_list(hooks: Any) -> list[str]:
        """Return a sanitised list of hook types, filtering out unknowns."""
        if not isinstance(hooks, list):
            return []
        valid: list[str] = []
        for h in hooks:
            if isinstance(h, str) and h in ALL_HOOK_TYPES:
                valid.append(h)
        return valid

    @staticmethod
    def _format_version_range(
        min_ver: str | None,
        max_ver: str | None,
    ) -> str:
        """Build a human-readable version range description."""
        if min_ver and max_ver:
            return f"{min_ver} ≤ version < {max_ver}"
        if min_ver:
            return f"≥ {min_ver}"
        if max_ver:
            return f"< {max_ver}"
        return "any"


__all__ = [
    "PluginManifest",
    "ManifestValidator",
    "REQUIRED_FIELDS",
    "ALL_HOOK_TYPES",
    "_version_satisfies",
    "_parse_version",
]
