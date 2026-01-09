"""
Configuration management for crypto-trading-volume application.
Loads configuration from environment variables with sensible defaults.
"""
import os
from typing import Optional


class Config:
    """Application configuration class."""
    
    # Flask Configuration
    FLASK_ENV: str = os.environ.get('FLASK_ENV', 'development')
    FLASK_APP: str = os.environ.get('FLASK_APP', 'web_dashboard.py')
    FLASK_SECRET_KEY: str = os.environ.get('FLASK_SECRET_KEY', '')
    DEBUG: bool = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Database Configuration
    DATABASE_PATH: str = os.environ.get('DATABASE_PATH', 'users.db')
    
    # Redis Configuration
    REDIS_URL: str = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_CACHE_EXPIRY: int = int(os.environ.get('REDIS_CACHE_EXPIRY', '60'))
    
    # Celery Configuration
    CELERY_BROKER_URL: str = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND: str = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # Email Configuration
    SMTP_HOST: Optional[str] = os.environ.get('SMTP_HOST')
    SMTP_PORT: Optional[int] = int(os.environ.get('SMTP_PORT', '0')) if os.environ.get('SMTP_PORT') else None
    SMTP_USER: Optional[str] = os.environ.get('SMTP_USER')
    SMTP_PASSWORD: Optional[str] = os.environ.get('SMTP_PASSWORD')
    SMTP_FROM: Optional[str] = os.environ.get('SMTP_FROM')
    
    # API Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '60'))
    
    # Application Settings
    HOST: str = os.environ.get('HOST', '0.0.0.0')
    PORT: int = int(os.environ.get('PORT', '5000'))
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production mode."""
        return cls.FLASK_ENV.lower() == 'production'
    
    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development mode."""
        return cls.FLASK_ENV.lower() == 'development'
    
    @classmethod
    def email_configured(cls) -> bool:
        """Check if email configuration is complete."""
        return all([
            cls.SMTP_HOST,
            cls.SMTP_PORT,
            cls.SMTP_USER,
            cls.SMTP_PASSWORD
        ])

