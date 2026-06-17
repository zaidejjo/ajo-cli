#!/usr/bin/env python3
"""Entry point for ``python -m ajo``.

Delegates to :func:`ajo.main` which handles the ``--version`` fast-path
before importing any heavy modules.
"""

from __future__ import annotations

import sys
from ajo import main

if __name__ == "__main__":
    sys.exit(main())
