"""
Utility functions for crypto-trading-volume application.
"""
import os
import secrets
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_secret_key() -> str:
    """Generate a secure secret key for Flask."""
    return secrets.token_hex(32)


def validate_environment() -> Dict[str, Any]:
    """
    Validate that required environment variables are set.
    Returns a dictionary with validation results.
    """
    results = {
        'valid': True,
        'warnings': [],
        'errors': [],
        'missing_required': [],
        'missing_optional': []
    }
    
    # Required in production
    required_prod = ['FLASK_SECRET_KEY']
    
    # Optional but recommended
    optional = [
        'REDIS_URL', 'SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD',
        'DATABASE_PATH', 'CELERY_BROKER_URL'
    ]
    
    is_production = os.environ.get('FLASK_ENV', '').lower() == 'production'
    
    if is_production:
        for var in required_prod:
            if not os.environ.get(var):
                results['missing_required'].append(var)
                results['errors'].append(f"Required environment variable {var} is not set in production")
                results['valid'] = False
    
    for var in optional:
        if not os.environ.get(var):
            results['missing_optional'].append(var)
            results['warnings'].append(f"Optional environment variable {var} is not set")
    
    return results


def format_currency(value: float, currency: str = 'USD') -> str:
    """Format a number as currency."""
    if currency == 'USD':
        return f"${value:,.2f}"
    return f"{value:,.2f} {currency}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format a number as percentage."""
    return f"{value:.{decimals}f}%"


def format_large_number(value: float) -> str:
    """Format large numbers with K, M, B suffixes."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:.2f}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def log_error(error: Exception, context: Optional[str] = None):
    """Log an error with context."""
    message = f"Error: {str(error)}"
    if context:
        message = f"{context} - {message}"
    logger.error(message, exc_info=True)


def validate_coin_symbol(symbol: str) -> bool:
    """Validate a cryptocurrency symbol."""
    if not symbol or not isinstance(symbol, str):
        return False
    # Basic validation: alphanumeric, 2-10 characters
    return symbol.isalnum() and 2 <= len(symbol) <= 10


def validate_exchange_name(exchange: str) -> bool:
    """Validate an exchange name."""
    valid_exchanges = ['binance', 'coinbase', 'kraken', 'kucoin', 'okx', 'bybit']
    return exchange.lower() in valid_exchanges

