"""Structured settings.py parser and injector for add-on modules.

The :class:`SettingsInjector` uses regex to locate insertion points
in ``settings.py`` (``INSTALLED_APPS``, ``MIDDLEWARE``, end-of-file)
so that add-ons can inject configuration without fragile string
matching.

Usage::

    from ajo.presets.addons._settings import SettingsInjector

    text = settings_path.read_text()
    text = SettingsInjector.inject_apps(text, ["myapp"])
    text = SettingsInjector.inject_middleware(
        text,
        [("my.middleware.Class", "first")],
    )
    text = SettingsInjector.append_block(text, "CACHES = {...}")
    settings_path.write_text(text)
"""

from __future__ import annotations

import re
from typing import Literal

# ── Patterns ────────────────────────────────────────────────────────────

INSTALLED_APPS_PATTERN = re.compile(
    r"^(INSTALLED_APPS\s*=\s*\[)",
    re.MULTILINE,
)
"""Matches ``INSTALLED_APPS = [`` (the opening bracket)."""

MIDDLEWARE_PATTERN = re.compile(
    r"^(MIDDLEWARE\s*=\s*\[)",
    re.MULTILINE,
)
"""Matches ``MIDDLEWARE = [`` (the opening bracket)."""

_LIST_CLOSE_PATTERN = re.compile(r"^\]", re.MULTILINE)
"""Matches a ``]`` at the start of a line. Used to find the end of
a list literal when we need to insert before/after specific positions."""


class SettingsInjector:
    """Registry of static methods for injecting into ``settings.py``."""

    # ── Public API ──────────────────────────────────────────────────────

    @classmethod
    def inject_apps(
        cls,
        settings_text: str,
        apps: list[str],
    ) -> str:
        """Add dotted app paths to the ``INSTALLED_APPS`` list.

        Apps are injected as a single block after the opening ``[``.
        Duplicate entries are silently skipped.

        Args:
            settings_text: The full ``settings.py`` content.
            apps: List of app label strings (e.g. ``["myapp", "corsheaders"]``).

        Returns:
            Updated settings content.
        """
        return cls._inject_list(
            settings_text,
            INSTALLED_APPS_PATTERN,
            apps,
            header_comment="Add-ons",
        )

    @classmethod
    def inject_middleware(
        cls,
        settings_text: str,
        middleware: list[tuple[str, Literal["first", "last"]]],
    ) -> str:
        """Inject middleware classes into the ``MIDDLEWARE`` list.

        Each item is a ``(dotted_path, position)`` tuple where position
        is ``"first"`` (insert right after opening ``[``) or ``"last"``
        (insert right before closing ``]``).

        Args:
            settings_text: The full ``settings.py`` content.
            middleware: List of ``(path, position)`` tuples.

        Returns:
            Updated settings content.
        """
        lines = settings_text.split("\n")
        new_lines: list[str] = []
        in_middleware = False
        middleware_appended = False
        middleware_inserted = False
        first_items: list[str] = [
            _fmt_middleware(p) for p, pos in middleware if pos == "first"
        ]
        last_items: list[str] = [
            _fmt_middleware(p) for p, pos in middleware if pos == "last"
        ]

        for i, line in enumerate(lines):
            if not in_middleware and MIDDLEWARE_PATTERN.match(line):
                in_middleware = True
                new_lines.append(line)
                if first_items:
                    new_lines.extend(first_items)
                    middleware_inserted = True
                continue

            if in_middleware:
                stripped = line.strip()
                # Detect closing bracket (at any indent level)
                if stripped == "]" and _count_brackets(lines, i) == 0:
                    if last_items and not middleware_appended:
                        new_lines.extend(last_items)
                        middleware_appended = True
                    new_lines.append(line)
                    in_middleware = False
                    continue
                # Skip existing entries that match to avoid duplicates
                if in_middleware and any(p in line for p, _ in middleware):
                    continue

            new_lines.append(line)

        return "\n".join(new_lines)

    @classmethod
    def append_block(
        cls,
        settings_text: str,
        block: str,
    ) -> str:
        """Append a raw Python code block to the end of ``settings.py``.

        A blank line is added before the block if the file does not
        already end with one.

        Args:
            settings_text: The full ``settings.py`` content.
            block: Python source code block to append.

        Returns:
            Updated settings content.
        """
        text = settings_text.rstrip("\n")
        if text and not text.endswith("\n\n"):
            text += "\n\n"
        return text + block + "\n"

    @classmethod
    def inject_env(
        cls,
        env_text: str,
        env_vars: dict[str, str],
    ) -> str:
        """Append environment variables to a ``.env`` file.

        Skips variables that already exist in the file.

        Args:
            env_text: The full ``.env`` content.
            env_vars: Dict of ``{KEY: value}`` pairs.

        Returns:
            Updated ``.env`` content.
        """
        existing = set()
        for line in env_text.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                existing.add(key)

        # Nothing to inject — return unchanged
        if not env_vars:
            return env_text

        lines = list(env_text.rstrip("\n").split("\n")) if env_text.strip() else []
        if lines and lines[-1] != "":
            lines.append("")

        for key, value in env_vars.items():
            if key not in existing:
                lines.append(f"{key}={value}")

        return "\n".join(lines) + "\n" if lines else ""

    @classmethod
    def inject_urls(
        cls,
        urls_text: str,
        url_patterns: list[tuple[str, str]],
    ) -> str:
        """Add ``path()`` entries to ``urlpatterns`` in ``urls.py``.

        Each entry is a ``(route, import_path_or_view)`` tuple.

        Args:
            urls_text: The full ``urls.py`` content.
            url_patterns: List of ``(path, import_string)`` tuples.

        Returns:
            Updated ``urls.py`` content.
        """
        # If empty list, return unchanged
        if not url_patterns:
            return urls_text

        # Find urlpatterns list and inject before the closing ]
        urlpatterns_pattern = re.compile(r"(urlpatterns\s*=\s*\[)")
        match = urlpatterns_pattern.search(urls_text)

        # Determine if we need ``include()``
        def _is_include(imp: str) -> bool:
            return imp.endswith(".urls") or ".urlpatterns" in imp

        needs_include = any(_is_include(imp) for _, imp in url_patterns)

        if not match:
            # No urlpatterns found — append at end
            path_lines = []
            for route, imp in url_patterns:
                if _is_include(imp):
                    path_lines.append(f"    path('{route}', include('{imp}')),")
                else:
                    path_lines.append(f"    path('{route}', {_extract_name(imp)}),")
            imports_lines = []
            if needs_include:
                imports_lines.append("from django.urls import include")
            for _, imp in url_patterns:
                imports_lines.append(
                    f"from {_extract_module(imp)} import {_extract_name(imp)}"
                )
            block = (
                "\n"
                + "\n".join(imports_lines)
                + "\n\n"
                + "urlpatterns = [\n"
                + "\n".join(path_lines)
                + "\n]\n"
            )
            return urls_text.rstrip() + "\n" + block

        lines = urls_text.split("\n")

        # Calculate the line number of the matched urlpatterns bracket
        match_line = urls_text[: match.start()].count("\n")

        # Insert imports at the top (after docstring if any)
        new_imports: list[str] = []
        if needs_include and "include" not in urls_text:
            new_imports.append("from django.urls import include")
        for _, imp in url_patterns:
            mod = _extract_module(imp)
            name = _extract_name(imp)
            if not any(imp in l or name in l for l in lines):
                new_imports.append(f"from {mod} import {name}")
        if new_imports:
            import_idx = cls._find_import_insert_point(lines)
            for ni in reversed(new_imports):
                lines.insert(import_idx, ni)
            # Adjust match_line if imports were inserted before it
            if import_idx <= match_line:
                match_line += len(new_imports)

        # Insert path entries before the closing ]
        insert_pos = cls._find_list_end(lines, match_line)
        if insert_pos is None:
            # Fallback: use the urlpatterns-aware _url_block
            return urls_text.rstrip() + "\n" + _url_block(url_patterns, needs_include)

        path_entries: list[str] = []
        for route, imp in url_patterns:
            if _is_include(imp):
                path_entries.append(f"    path('{route}', include('{imp}')),")
            else:
                path_entries.append(f"    path('{route}', {_extract_name(imp)}),")
        for pe in reversed(path_entries):
            lines.insert(insert_pos, pe)

        return "\n".join(lines)

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _inject_list(
        text: str,
        pattern: re.Pattern[str],
        items: list[str],
        *,
        header_comment: str = "",
    ) -> str:
        """Insert items into a list literal matched by *pattern*.

        Items are deduplicated against existing entries.  Returns the
        original text if the pattern is not found.
        """
        match = pattern.search(text)
        if not match:
            return text  # Pattern not found — return unchanged

        # Split at the match end (the opening bracket)
        pos = match.end()
        before = text[:pos]
        after = text[pos:]

        # Collect existing entries for dedup
        existing = set()
        for line in after.split("\n"):
            raw = line.strip().strip(",").strip("'").strip('"')
            if raw and not line.strip().startswith("#"):
                existing.add(raw)

        # Filter out duplicates
        new_items = [it for it in items if it not in existing]
        if not new_items:
            return text  # Nothing to inject

        # Build the injection block
        block_parts: list[str] = []
        if header_comment:
            block_parts.append(f"    # ── {header_comment} ──")
        for item in new_items:
            block_parts.append(f"    '{item}',")

        # Insert right after the opening bracket
        return before + "\n" + "\n".join(block_parts) + "\n" + after

    @staticmethod
    def _find_list_end(lines: list[str], start_line: int) -> int | None:
        """Find the line index of the closing ``]`` for a list literal.

        Starts scanning at *start_line*.  Returns ``None`` if not found.
        """
        depth = 0
        for i in range(start_line, len(lines)):
            stripped = lines[i].strip()
            if "[" in stripped:
                depth += stripped.count("[")
            if "]" in stripped:
                depth -= stripped.count("]")
                if depth <= 0:
                    return i
        return None

    @staticmethod
    def _find_import_insert_point(lines: list[str]) -> int:
        """Find the best line index for inserting new imports.

        Prefers after the module docstring, or at line 1 if no docstring.
        """
        in_docstring = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    continue  # Single-line docstring
                in_docstring = not in_docstring
                continue
            if in_docstring:
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    in_docstring = False
                continue
            if stripped.startswith("from ") or stripped.startswith("import "):
                return i  # Found existing imports — insert before first one
        # No imports found — insert after line 1 (after docstring)
        return 1 if len(lines) > 1 else 0


# ── Module-level helpers ────────────────────────────────────────────────


def _fmt_middleware(path: str) -> str:
    """Format a middleware class path as a Python string literal line."""
    return f"    '{path}',"


def _extract_module(import_path: str) -> str:
    """Extract the module part from a dotted import path.

    Handles both regular imports and ``module:attr`` notation:

    ``"myapp.api.views.MyView"`` → ``"myapp.api.views"``
    ``"debug_toolbar.toolbar:debug_toolbar_urlpatterns"`` → ``"debug_toolbar.toolbar"``
    """
    # Handle module:attr notation
    if ":" in import_path:
        return import_path.split(":", 1)[0]
    parts = import_path.rsplit(".", 1)
    return parts[0] if len(parts) > 1 else import_path


def _extract_name(import_path: str) -> str:
    """Extract the name part from a dotted import path.

    Handles both regular imports and ``module:attr`` notation:

    ``"myapp.api.views.MyView"`` → ``"MyView"``
    ``"debug_toolbar.toolbar:debug_toolbar_urlpatterns"`` → ``"debug_toolbar_urlpatterns"``
    """
    # Handle module:attr notation
    if ":" in import_path:
        return import_path.split(":", 1)[1]
    return import_path.rsplit(".", 1)[-1]


def _url_block(url_patterns: list[tuple[str, str]], needs_include: bool = False) -> str:
    """Generate a complete ``urlpatterns`` block for fallback insertion."""
    imports = set()
    for route, imp in url_patterns:
        imports.add(f"from {_extract_module(imp)} import {_extract_name(imp)}")
    lines = [
        "",
        *sorted(imports),
        "",
        "urlpatterns = [",
    ]
    for route, imp in url_patterns:
        if needs_include and (imp.endswith(".urls") or ".urlpatterns" in imp):
            lines.append(f"    path('{route}', include('{imp}')),")
        else:
            lines.append(f"    path('{route}', {_extract_name(imp)}),")
    lines.append("]")
    if needs_include:
        lines.insert(1, "from django.urls import include")
    return "\n".join(lines) + "\n"


def _count_brackets(lines: list[str], current_idx: int) -> int:
    """Count unclosed ``[`` brackets up to *current_idx*.

    Used to distinguish the closing ``]`` of ``MIDDLEWARE`` from
    other list closures.
    """
    depth = 0
    for line in lines[: current_idx + 1]:
        depth += line.count("[")
        depth -= line.count("]")
    return depth
