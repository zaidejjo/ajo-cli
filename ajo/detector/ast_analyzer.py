"""AST-based model relationship analyzer for Django projects.

Parses ``models.py`` files using Python's ``ast`` module (zero-execution)
to extract model definitions, field types, and relationship metadata
(ForeignKey, OneToOneField, ManyToManyField).  This information can then
be consumed by presets to auto-generate serializers, viewsets, and URL
confs — all without importing or executing the target code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Final


# ── Data containers ─────────────────────────────────────────────────────────


class ModelRelationship:
    """Describes a single Django model and its fields/relations.

    Attributes:
        model_name: The class name of the model (e.g. ``"Book"``).
        fields: A list of field descriptors, each with ``name``, ``type``,
            and optional ``args``.
        relations: A list of relationship descriptors, each with ``type``,
            ``to``, and optional ``related_name`` / ``through``.
    """

    __slots__ = ("model_name", "fields", "relations")

    def __init__(
        self,
        model_name: str,
        fields: list[dict[str, Any]],
        relations: list[dict[str, str]],
    ) -> None:
        self.model_name = model_name
        self.fields = fields
        self.relations = relations

    def __repr__(self) -> str:
        return (
            f"ModelRelationship(name={self.model_name!r}, "
            f"fields={len(self.fields)}, relations={len(self.relations)})"
        )


# ── AST Analyzer ────────────────────────────────────────────────────────────


class ModelRelationshipAnalyzer:
    """Analyse a Django project's ``models.py`` files via AST parsing.

    Key design decisions:

    * **Zero-execution** — uses ``ast.parse``, never ``import`` or ``exec``.
    * **Resilient** — skips files with ``SyntaxError``, missing directories,
      or permission errors without crashing.
    * **Extensible** — the ``KNOWN_FIELDS`` and ``RELATION_FIELDS`` frozensets
      can be augmented for custom field types.

    Usage::

        analyzer = ModelRelationshipAnalyzer(Path("/path/to/project"))
        models = analyzer.analyze()
        for name, rel in models.items():
            print(f"{name}: {len(rel.relations)} relation(s)")
    """

    #: Field types recognised as standard Django model fields.
    KNOWN_FIELDS: Final[frozenset[str]] = frozenset(
        {
            "CharField",
            "IntegerField",
            "BooleanField",
            "DateField",
            "DateTimeField",
            "ForeignKey",
            "OneToOneField",
            "ManyToManyField",
            "TextField",
            "EmailField",
            "URLField",
            "FileField",
            "ImageField",
            "DecimalField",
            "FloatField",
            "JSONField",
            "UUIDField",
            "SlugField",
            "AutoField",
            "BigAutoField",
            "SmallAutoField",
            "PositiveIntegerField",
            "SmallIntegerField",
            "BigIntegerField",
            "DurationField",
            "TimeField",
            "BinaryField",
            "GenericIPAddressField",
        }
    )

    #: Subset of KNOWN_FIELDS that represent database relations.
    RELATION_FIELDS: Final[frozenset[str]] = frozenset(
        {
            "ForeignKey",
            "OneToOneField",
            "ManyToManyField",
        }
    )

    #: Compiled regex for CamelCase-to-kebab-case conversion.
    _CAMEL_TO_KEBAB: Final[re.Pattern[str]] = re.compile(r"(?<!^)(?=[A-Z])")

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path.resolve()
        #: Discovered models keyed by class name.
        self.models: dict[str, ModelRelationship] = {}

    # ── Public API ───────────────────────────────────────────────────────

    def analyze(self) -> dict[str, ModelRelationship]:
        """Walk the project tree, parse every ``models.py``, and collect models.

        Returns:
            A dict mapping model class names to :class:`ModelRelationship`
            instances.
        """
        self.models.clear()
        for app_path in self._discover_app_dirs():
            models_file = app_path / "models.py"
            if models_file.is_file():
                self._parse_models_file(models_file)
        return self.models

    def analyze_single_file(self, path: Path) -> dict[str, ModelRelationship]:
        """Parse a single ``models.py`` file and return discovered models.

        This is useful when you already know the exact file path
        (e.g. after ``manage.py startapp``).

        Args:
            path: Path to a ``models.py`` file.

        Returns:
            A dict of model class names to :class:`ModelRelationship`.
        """
        self.models.clear()
        if path.is_file():
            self._parse_models_file(path)
        return self.models

    # ── App discovery ────────────────────────────────────────────────────

    def _discover_app_dirs(self) -> list[Path]:
        """Discover Django app directories in the project root.

        An app directory is a sub-directory that contains an ``apps.py``
        or a ``models.py`` file, and does not start with ``.``.
        """
        dirs: list[Path] = []
        try:
            for item in self.project_path.iterdir():
                if not item.is_dir() or item.name.startswith("."):
                    continue
                if (item / "apps.py").is_file() or (item / "models.py").is_file():
                    dirs.append(item)
        except PermissionError:
            pass
        return dirs

    # ── File parsing ─────────────────────────────────────────────────────

    def _parse_models_file(self, path: Path) -> None:
        """Parse a single ``models.py`` file and populate ``self.models``."""
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except SyntaxError:
            return  # Gracefully skip malformed files

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._process_class(node)

    def _process_class(self, node: ast.ClassDef) -> None:
        """Process a single class definition node.

        Only processes classes that inherit (directly or indirectly)
        from ``models.Model``.
        """
        if not self._inherits_from_model(node):
            return

        model_name: str = node.name
        fields: list[dict[str, Any]] = []
        relations: list[dict[str, str]] = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(
                        item.value, ast.Call
                    ):
                        field_info = self._extract_field_info(target.id, item.value)
                        if field_info is not None:
                            fields.append(field_info)
                            if field_info["type"] in self.RELATION_FIELDS:
                                relations.append(
                                    {
                                        "type": field_info["type"],
                                        "to": field_info.get("to", "Unknown"),
                                        "related_name": field_info.get(
                                            "related_name", ""
                                        ),
                                        "through": field_info.get("through", ""),
                                        "on_delete": field_info.get("on_delete", ""),
                                    }
                                )

        self.models[model_name] = ModelRelationship(model_name, fields, relations)

    # ── Inheritance detection ────────────────────────────────────────────

    @staticmethod
    def _inherits_from_model(node: ast.ClassDef) -> bool:
        """Check whether a class inherits from ``models.Model``.

        Handles both ``models.Model`` (attribute access) and
        local imports like ``from django.db import models`` followed
        by inheritance from just ``Model`` (name reference).
        """
        for base in node.bases:
            # Case: class Foo(models.Model):
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                return True
            # Case: from django.db import models; class Foo(Model):
            if isinstance(base, ast.Name) and base.id == "Model":
                return True
        return False

    # ── Field extraction ─────────────────────────────────────────────────

    @staticmethod
    def _extract_field_info(name: str, call: ast.Call) -> dict[str, Any] | None:
        """Extract field metadata from an assignment node.

        Args:
            name: The field name (e.g. ``"author"``).
            call: The ``ast.Call`` node representing the field
                  instantiation (e.g. ``ForeignKey(Author, ...)``).

        Returns:
            A dict with keys ``name``, ``type``, plus any keyword
            arguments, or ``None`` if the call is not a recognised field.
        """
        if not isinstance(call.func, ast.Attribute):
            return None

        field_type: str = call.func.attr
        if field_type not in ModelRelationshipAnalyzer.KNOWN_FIELDS:
            return None

        info: dict[str, Any] = {"name": name, "type": field_type}

        # ── Positional arguments ─────────────────────────────────────
        for i, arg in enumerate(call.args):
            if isinstance(arg, ast.Name):
                if i == 0 and field_type in ModelRelationshipAnalyzer.RELATION_FIELDS:
                    info["to"] = arg.id
            elif isinstance(arg, ast.Constant):
                if i == 0:
                    info["to"] = arg.value

        # ── Keyword arguments ─────────────────────────────────────────
        for kw in call.keywords:
            if kw.arg is None:
                continue
            if isinstance(kw.value, ast.Constant):
                info[kw.arg] = kw.value.value
            elif isinstance(kw.value, ast.Name):
                info[kw.arg] = kw.value.id
            elif isinstance(kw.value, ast.Attribute):
                # Handle settings.AUTH_USER_MODEL style references
                prefix = ""
                if isinstance(kw.value.value, ast.Name):
                    prefix = kw.value.value.id
                elif isinstance(kw.value.value, ast.Attribute):
                    prefix = f"{kw.value.value.attr}.{kw.value.attr}"
                info[kw.arg] = f"{prefix}.{kw.value.attr}" if prefix else kw.value.attr

        return info

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def model_name_to_route(model_name: str) -> str:
        """Convert a CamelCase model name to a kebab-case route.

        Examples::

            >>> ModelRelationshipAnalyzer.model_name_to_route("Book")
            'book'
            >>> ModelRelationshipAnalyzer.model_name_to_route("BlogPost")
            'blog-post'
        """
        return ModelRelationshipAnalyzer._CAMEL_TO_KEBAB.sub("-", model_name).lower()
