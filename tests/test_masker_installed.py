"""Tests that SecretMasker is installed on the evalite logger at import time."""

import logging

# Import evalite to trigger _install_masker() call at module load time
import evalite  # noqa: F401


class RecordCapture(logging.Handler):
    """Custom handler that captures log records for testing."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record: logging.LogRecord) -> None:
        """Store the record."""
        self.records.append(record)


def test_masker_installed_on_evalite_logger():
    """SecretMasker is installed on the evalite logger and redacts secrets."""
    logger = logging.getLogger("evalite")
    handler = RecordCapture()
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("token: Bearer abc123xyz")

    assert len(handler.records) == 1
    formatted = handler.records[0].getMessage()
    assert "[REDACTED]" in formatted
    assert "abc123xyz" not in formatted


def test_masker_scoped_to_evalite_logger_only():
    """SecretMasker is NOT attached to the root logger or other loggers."""
    # Get a logger NOT under the evalite namespace
    other_logger = logging.getLogger("some.other.library")
    handler = RecordCapture()
    other_logger.handlers = []
    other_logger.addHandler(handler)
    other_logger.setLevel(logging.INFO)

    # Log a message with a secret
    other_logger.info("token: Bearer secret123")

    # The secret should NOT be redacted on a non-evalite logger
    assert len(handler.records) == 1
    formatted = handler.records[0].getMessage()
    assert "secret123" in formatted
    assert "[REDACTED]" not in formatted


