"""Transactional scaffold engine and rollback management.

This package provides the atomic project-scaffolding pipeline:

* :class:`~ajo.scaffolding.engine.ScaffoldEngine` — orchestration of
  bootstrapping steps with automatic rollback on failure.
* :class:`~ajo.scaffolding.engine.RollbackManager` — LIFO undo journal
  for fine-grained cleanup.
"""

from ajo.scaffolding.engine import RollbackManager, ScaffoldEngine

__all__ = [
    "RollbackManager",
    "ScaffoldEngine",
]
