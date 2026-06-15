"""Django project detection, state caching, and smart command system.

This package provides the full detection pipeline:

* :class:`DjangoProjectDetector` — fast sync + async cached detection.
* :class:`DetectorCache` — filesystem-backed JSON cache with TTL.
* :class:`SmartDjangoCLI` — context-aware command prioritisation.
* :func:`check_prerequisites` — optimised binary checks via ``shutil.which``.
"""

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
]
