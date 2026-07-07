"""Tests for ajo.core.logging_config."""

from __future__ import annotations

import io
import logging

import pytest

from ajo.core.logging_config import (
    VERBOSITY_MAP,
    get_verbosity_level,
    set_verbosity,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Reset the ajo logger between tests."""
    logger = logging.getLogger("ajo")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    yield
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_default_level_is_warning(self) -> None:
        setup_logging(verbosity=0)
        logger = logging.getLogger("ajo")
        assert logger.level == logging.WARNING

    def test_verbose_level_is_info(self) -> None:
        setup_logging(verbosity=1)
        logger = logging.getLogger("ajo")
        assert logger.level == logging.INFO

    def test_very_verbose_level_is_debug(self) -> None:
        setup_logging(verbosity=2)
        logger = logging.getLogger("ajo")
        assert logger.level == logging.DEBUG

    def test_quiet_level_is_error(self) -> None:
        setup_logging(verbosity=-1)
        logger = logging.getLogger("ajo")
        assert logger.level == logging.ERROR

    def test_idempotent(self) -> None:
        """Second call without force=True does not add duplicate handlers."""
        setup_logging(verbosity=1)
        setup_logging(verbosity=1)
        logger = logging.getLogger("ajo")
        assert len(logger.handlers) == 1

    def test_force_reconfigures(self) -> None:
        """force=True clears and re-adds handlers."""
        setup_logging(verbosity=0)
        setup_logging(verbosity=2, force=True)
        logger = logging.getLogger("ajo")
        assert len(logger.handlers) == 1
        assert logger.level == logging.DEBUG

    def test_stream_parameter(self) -> None:
        """Custom stream is used when provided."""
        stream = io.StringIO()
        setup_logging(verbosity=1, stream=stream)
        logger = logging.getLogger("ajo")
        logger.info("test message")
        output = stream.getvalue()
        assert "test message" in output

    def test_non_propagating(self) -> None:
        """Logger does not propagate to root logger."""
        setup_logging(verbosity=1)
        logger = logging.getLogger("ajo")
        assert logger.propagate is False

    def test_quiet_overrides_at_debug(self) -> None:
        """Noisy sub-loggers are pinned to INFO when root is DEBUG."""
        setup_logging(verbosity=2)
        noisy = logging.getLogger("ajo.ui")
        assert noisy.level == logging.INFO


class TestVerbosityMap:
    """Tests for the verbosity mapping."""

    def test_all_levels_mapped(self) -> None:
        assert VERBOSITY_MAP[-1] == logging.ERROR
        assert VERBOSITY_MAP[0] == logging.WARNING
        assert VERBOSITY_MAP[1] == logging.INFO
        assert VERBOSITY_MAP[2] == logging.DEBUG


class TestGetVerbosityLevel:
    """Tests for get_verbosity_level conversion."""

    def test_converts_correctly(self) -> None:
        assert get_verbosity_level(-1) == logging.ERROR
        assert get_verbosity_level(0) == logging.WARNING
        assert get_verbosity_level(1) == logging.INFO
        assert get_verbosity_level(2) == logging.DEBUG

    def test_unknown_defaults_to_debug(self) -> None:
        assert get_verbosity_level(99) == logging.DEBUG


class TestSetVerbosity:
    """Tests for dynamic verbosity adjustment."""

    def test_dynamic_change(self) -> None:
        setup_logging(verbosity=0)
        set_verbosity(2)
        logger = logging.getLogger("ajo")
        assert logger.level == logging.DEBUG

    def test_quiet_overrides_applied_on_change(self) -> None:
        setup_logging(verbosity=2)
        set_verbosity(-1)
        logger = logging.getLogger("ajo")
        assert logger.level == logging.ERROR
