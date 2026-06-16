"""UI components for the ajo-cli TUI.

Heavy UI imports (Rich, InquirerPy) are NOT loaded at package level.
Access them through their specific submodules (``ajo.ui.theme``, etc.),
which themselves are lazy-loaded on first use.
"""

# No top-level imports — Rich / InquirerPy are loaded lazily on demand.

__all__: list[str] = []
