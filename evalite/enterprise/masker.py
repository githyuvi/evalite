"""Logging filter that redacts secret-looking substrings from log records."""

import logging
import re

DEFAULT_PATTERNS: list[str] = [
    r"Bearer\s+\S+",           # Bearer tokens
    r"api[_-]?key[=:]\s*\S+",  # API keys
    r"password[=:]\s*\S+",     # Passwords
]


class SecretMasker(logging.Filter):
    """Redacts matched patterns in log records before emission."""

    def __init__(self, patterns: list[str] = DEFAULT_PATTERNS) -> None:
        """Initialize the masker with compiled regex patterns.

        Args:
            patterns: List of regex pattern strings to match and redact.
                Defaults to DEFAULT_PATTERNS (Bearer tokens, API keys, passwords).
        """
        super().__init__()
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def filter(self, record: logging.LogRecord) -> bool:
        """Replaces matched patterns with [REDACTED] in record.msg and record.args.

        Args:
            record: The log record to filter.

        Returns:
            True (never filters out records, only masks content).
        """
        # Mask record.msg if it's a string and no args present (not %-style logging)
        # When args are present, record.msg is a format string and masking it
        # could break format placeholders; secrets are in args instead.
        if isinstance(record.msg, str) and not record.args:
            for pattern in self.patterns:
                record.msg = pattern.sub("[REDACTED]", record.msg)

        # Mask record.args if it's a tuple
        if isinstance(record.args, tuple):
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    masked_arg = arg
                    for pattern in self.patterns:
                        masked_arg = pattern.sub("[REDACTED]", masked_arg)
                    new_args.append(masked_arg)
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)

        # Mask record.args if it's a dict
        elif isinstance(record.args, dict):
            new_dict = {}
            for key, value in record.args.items():
                if isinstance(value, str):
                    masked_value = value
                    for pattern in self.patterns:
                        masked_value = pattern.sub("[REDACTED]", masked_value)
                    new_dict[key] = masked_value
                else:
                    new_dict[key] = value
            record.args = new_dict

        return True
