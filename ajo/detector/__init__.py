"""Django project detection, state caching, smart command system, and AST analysis.

This package provides the full detection pipeline:

* :class:`DjangoProjectDetector` — fast sync + async cached detection.
* :class:`DetectorCache` — filesystem-backed JSON cache with TTL.
* :class:`SmartDjangoCLI` — context-aware command prioritisation.
* :func:`check_prerequisites` — optimised binary checks via ``shutil.which``.
* :class:`ModelRelationshipAnalyzer` — zero-execution AST analysis of ``models.py``
  for auto-generating serializers, viewsets, and URLs.
* :class:`ModelRelationship` — data container for discovered model metadata.
"""

# ── Lazy re-exports for fast startup ─────────────────────────────────────
# Most imports below are direct to avoid circular dependencies.
# Heavy modules (ast_analyzer) use lazy import within the functions that
# need them — the re-exports here are just for convenience.

from ajo.detector.cache import DetectorCache
from ajo.detector.prereqs import (
    PrereqResult,
    check_prerequisites,
    check_uv_installed,
    check_git_installed,
    check_gh_installed,
)
from ajo.detector.project import DjangoProjectDetector, RuffResult
from ajo.detector.smart_cli import SmartCommand, SmartDjangoCLI

# AST Analyzer (lazy evaluation at module level — actual parsing only
# happens when the user calls analyze()).
from ajo.detector.ast_analyzer import ModelRelationship, ModelRelationshipAnalyzer  # noqa: E402, F401

__all__ = [
    "DjangoProjectDetector",
    "DetectorCache",
    "RuffResult",
    "SmartCommand",
    "SmartDjangoCLI",
    "PrereqResult",
    "check_prerequisites",
    "check_uv_installed",
    "check_git_installed",
    "check_gh_installed",
    "ModelRelationship",
    "ModelRelationshipAnalyzer",
]
