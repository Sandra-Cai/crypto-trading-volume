import os
import logging

from utils import safe_getenv


def test_safe_getenv_returns_default_when_missing():
    key = "UTILS_TEST_MISSING_VAR"
    os.environ.pop(key, None)
    assert safe_getenv(key, default="fallback") == "fallback"


def test_safe_getenv_reads_existing_value():
    key = "UTILS_TEST_EXISTING_VAR"
    os.environ[key] = "value123"
    assert safe_getenv(key) == "value123"


def test_safe_getenv_logs_warning_when_required_and_missing(caplog):
    key = "UTILS_TEST_REQUIRED_MISSING"
    os.environ.pop(key, None)
    with caplog.at_level(logging.WARNING):
        result = safe_getenv(key, default=None, required=True)
    assert result is None
    # At least one warning mentioning the variable name should be logged
    assert any(key in record.getMessage() for record in caplog.records)

