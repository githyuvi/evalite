"""Tests for the SecretMasker logging filter."""

import logging

from evalite.enterprise.masker import DEFAULT_PATTERNS, SecretMasker


class RecordCapture(logging.Handler):
    """Custom handler that captures log records for testing."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record: logging.LogRecord) -> None:
        """Store the record."""
        self.records.append(record)


def test_bearer_token_masking():
    """Bearer tokens are redacted in record.msg."""
    logger = logging.getLogger("test_bearer")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Authorization: Bearer abc123token")

    assert len(handler.records) == 1
    # Pattern matches "Bearer abc123token" together and replaces with [REDACTED]
    assert handler.records[0].msg == "Authorization: [REDACTED]"


def test_bearer_token_masking_case_insensitive():
    """Bearer tokens are redacted case-insensitively."""
    logger = logging.getLogger("test_bearer_case")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Authorization: bearer xyz789")

    assert len(handler.records) == 1
    assert handler.records[0].msg == "Authorization: [REDACTED]"


def test_api_key_masking():
    """API keys are redacted."""
    logger = logging.getLogger("test_api_key")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("API_KEY=secret123")

    assert len(handler.records) == 1
    assert handler.records[0].msg == "[REDACTED]"


def test_password_masking():
    """Passwords are redacted."""
    logger = logging.getLogger("test_password")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("password=mypassword123")

    assert len(handler.records) == 1
    assert handler.records[0].msg == "[REDACTED]"


def test_custom_pattern_masking():
    """Custom patterns are applied correctly."""
    logger = logging.getLogger("test_custom")
    logger.handlers = []
    handler = RecordCapture()
    custom_pattern = r"secret[=:]\s*\S+"
    masker = SecretMasker(patterns=[custom_pattern])
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("My secret=confidential_value")

    assert len(handler.records) == 1
    assert handler.records[0].msg == "My [REDACTED]"


def test_no_secrets_passes_through():
    """Records without secrets pass through unchanged."""
    logger = logging.getLogger("test_no_secrets")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    original_msg = "This is a normal log message"
    logger.info(original_msg)

    assert len(handler.records) == 1
    assert handler.records[0].msg == original_msg


def test_non_string_record_msg_doesnt_raise():
    """Non-string record.msg doesn't raise an exception."""
    logger = logging.getLogger("test_non_string")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Create a record manually with non-string msg
    record = logger.makeRecord(
        logger.name, logging.INFO, "test.py", 1, 12345, None, None
    )
    handler.handle(record)

    # Should not raise, filter should return True
    assert len(handler.records) == 1
    assert handler.records[0].msg == 12345  # Unchanged


def test_percent_style_logging_with_secret_in_args():
    """Secrets in record.args are redacted with %-style logging."""
    logger = logging.getLogger("test_percent_style")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Authorization: %s", "Bearer secret123")

    assert len(handler.records) == 1
    # The formatted message should have the secret redacted
    formatted = handler.records[0].getMessage()
    assert "Bearer secret123" not in formatted
    assert "[REDACTED]" in formatted


def test_tuple_args_with_multiple_values():
    """Multiple values in tuple args are all masked if they match."""
    logger = logging.getLogger("test_tuple_args")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Key: %s, Password: %s", "api_key=secret1", "password=secret2")

    assert len(handler.records) == 1
    formatted = handler.records[0].getMessage()
    assert "secret1" not in formatted
    assert "secret2" not in formatted
    assert "[REDACTED]" in formatted


def test_dict_args_with_secrets():
    """Secrets in dict args are redacted."""
    logger = logging.getLogger("test_dict_args")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # %-style logging with named placeholders uses dict args
    logger.info("Token: %(token)s", {"token": "Bearer abc123"})

    assert len(handler.records) == 1
    formatted = handler.records[0].getMessage()
    assert "abc123" not in formatted
    assert "[REDACTED]" in formatted


def test_filter_always_returns_true():
    """filter() always returns True (never drops records)."""
    masker = SecretMasker()
    logger = logging.getLogger("test_return_true")
    record = logger.makeRecord(
        logger.name, logging.INFO, "test.py", 1, "Test message", None, None
    )

    result = masker.filter(record)

    assert result is True


def test_multiple_patterns_in_one_message():
    """Multiple secrets in one message are all redacted."""
    logger = logging.getLogger("test_multiple")
    logger.handlers = []
    handler = RecordCapture()
    masker = SecretMasker()
    handler.addFilter(masker)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Bearer token1 and api_key=secret2 with password=secret3")

    assert len(handler.records) == 1
    msg = handler.records[0].msg
    assert "token1" not in msg
    assert "secret2" not in msg
    assert "secret3" not in msg
    # Should have multiple [REDACTED] placeholders
    assert msg.count("[REDACTED]") >= 3
