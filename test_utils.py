import os
import logging

from utils import (
    safe_getenv,
    format_currency,
    format_percentage,
    format_large_number,
    safe_divide,
    validate_coin_symbol,
    validate_exchange_name,
    get_timestamp,
    generate_secret_key,
    validate_environment,
)


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


def test_format_currency_usd():
    assert format_currency(1234.56) == "$1,234.56"
    assert format_currency(0) == "$0.00"


def test_format_currency_other():
    assert format_currency(100, "EUR") == "100.00 EUR"


def test_format_percentage():
    assert format_percentage(50.5) == "50.50%"
    assert format_percentage(33.333, decimals=1) == "33.3%"


def test_format_large_number():
    assert format_large_number(1_500_000_000) == "1.50B"
    assert format_large_number(2_000_000) == "2.00M"
    assert format_large_number(3_500) == "3.50K"
    assert format_large_number(99.5) == "99.50"


def test_safe_divide():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(10, 0) == 0.0
    assert safe_divide(10, 0, default=99.0) == 99.0


def test_validate_coin_symbol():
    assert validate_coin_symbol("BTC") is True
    assert validate_coin_symbol("ethereum") is True
    assert validate_coin_symbol("x") is False
    assert validate_coin_symbol("") is False
    assert validate_coin_symbol("a" * 11) is False
    assert validate_coin_symbol("BT-C") is False


def test_validate_exchange_name():
    assert validate_exchange_name("binance") is True
    assert validate_exchange_name("BINANCE") is True
    assert validate_exchange_name("unknown") is False


def test_get_timestamp():
    ts = get_timestamp()
    assert "T" in ts
    assert len(ts) >= 19


def test_generate_secret_key():
    key = generate_secret_key()
    assert isinstance(key, str)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_validate_environment_development(monkeypatch):
    # In development, missing FLASK_SECRET_KEY should not mark config as invalid
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    result = validate_environment()
    assert result["valid"] is True
    assert "FLASK_SECRET_KEY" not in result["missing_required"]


def test_validate_environment_production_missing_required(monkeypatch):
    # In production, missing FLASK_SECRET_KEY should fail validation
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    result = validate_environment()
    assert result["valid"] is False
    assert "FLASK_SECRET_KEY" in result["missing_required"]
    assert any("FLASK_SECRET_KEY" in msg for msg in result["errors"])


def test_validate_environment_production_all_set(monkeypatch):
    # In production, having all required variables should pass validation
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("FLASK_SECRET_KEY", "super-secret")
    # Optional variables can be set to any non-empty values
    optional_vars = [
        "REDIS_URL",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "DATABASE_PATH",
        "CELERY_BROKER_URL",
    ]
    for name in optional_vars:
        monkeypatch.setenv(name, "value")

    result = validate_environment()
    assert result["valid"] is True
    assert result["missing_required"] == []
    assert result["errors"] == []

