"""
LogicGate Configuration Management
Centralized configuration with pydantic-settings for environment-based configuration.
"""

from enum import StrEnum

# Try to import pydantic-settings, fall back to basic dict-based config
try:
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseSettings = object
    Field = lambda default=None, **kwargs: default  # noqa: E731
    field_validator = lambda *args, **kwargs: lambda func: func  # noqa: E731


class Environment(StrEnum):
    """Application environment"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseSettings(BaseSettings):
    """Database configuration"""

    url: str = Field(default="sqlite:///logicgate_shared.db", env="DATABASE_URL")
    async_url: str = Field(
        default="sqlite+aiosqlite:///logicgate_shared.db", env="ASYNC_DATABASE_URL"
    )
    pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    echo: bool = Field(default=False, env="DB_ECHO")

    class Config:
        env_prefix = "DB"


class CacheSettings(BaseSettings):
    """Cache configuration"""

    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: str | None = Field(default=None, env="REDIS_PASSWORD")
    default_ttl: int = Field(default=300, env="CACHE_DEFAULT_TTL")
    max_size: int = Field(default=10000, env="CACHE_MAX_SIZE")

    class Config:
        env_prefix = "CACHE"


class APISettings(BaseSettings):
    """API configuration"""

    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    workers: int = Field(default=4, env="API_WORKERS")
    reload: bool = Field(default=False, env="API_RELOAD")
    cors_origins: list[str] = Field(default=["*"], env="CORS_ORIGINS")
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    class Config:
        env_prefix = "API"


class WebSocketSettings(BaseSettings):
    """WebSocket configuration"""

    host: str = Field(default="0.0.0.0", env="WS_HOST")
    port: int = Field(default=8765, env="WS_PORT")
    max_connections: int = Field(default=1000, env="WS_MAX_CONNECTIONS")
    message_queue_size: int = Field(default=1000, env="WS_QUEUE_SIZE")
    heartbeat_interval: int = Field(default=30, env="WS_HEARTBEAT_INTERVAL")

    class Config:
        env_prefix = "WS"


class SecuritySettings(BaseSettings):
    """Security configuration"""

    secret_key: str = Field(default="change-me-in-production", env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    bcrypt_rounds: int = Field(default=12, env="BCRYPT_ROUNDS")
    mfa_enabled: bool = Field(default=True, env="MFA_ENABLED")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v, info):
        """Validate secret key in production"""
        # This validation would need access to the parent environment
        # For now, we'll skip this validation or move it to a model validator
        return v

    class Config:
        env_prefix = "SECURITY"


class LoggingSettings(BaseSettings):
    """Logging configuration"""

    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="json", env="LOG_FORMAT")
    file_path: str | None = Field(default=None, env="LOG_FILE_PATH")
    max_bytes: int = Field(default=10485760, env="LOG_MAX_BYTES")  # 10MB
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    sentry_dsn: str | None = Field(default=None, env="SENTRY_DSN")
    sentry_environment: str = Field(default="development", env="SENTRY_ENVIRONMENT")

    class Config:
        env_prefix = "LOG"


class MonitoringSettings(BaseSettings):
    """Monitoring configuration"""

    enabled: bool = Field(default=True, env="MONITORING_ENABLED")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    prometheus_enabled: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    trace_enabled: bool = Field(default=True, env="TRACE_ENABLED")

    class Config:
        env_prefix = "MONITORING"


class CelerySettings(BaseSettings):
    """Celery configuration"""

    broker_url: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    result_backend: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    task_serializer: str = Field(default="json", env="CELERY_TASK_SERIALIZER")
    accept_content: list[str] = Field(default=["json"], env="CELERY_ACCEPT_CONTENT")
    timezone: str = Field(default="UTC", env="CELERY_TIMEZONE")
    task_track_started: bool = Field(default=True, env="CELERY_TASK_TRACK_STARTED")
    task_time_limit: int = Field(default=300, env="CELERY_TASK_TIME_LIMIT")

    class Config:
        env_prefix = "CELERY"


class StorageSettings(BaseSettings):
    """Storage configuration"""

    local_path: str = Field(default="./storage", env="STORAGE_LOCAL_PATH")
    s3_enabled: bool = Field(default=False, env="S3_ENABLED")
    s3_bucket: str | None = Field(default=None, env="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", env="S3_REGION")
    s3_access_key: str | None = Field(default=None, env="S3_ACCESS_KEY")
    s3_secret_key: str | None = Field(default=None, env="S3_SECRET_KEY")

    class Config:
        env_prefix = "STORAGE"


class Settings(BaseSettings):
    """Main application settings"""

    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    app_name: str = Field(default="LogicGate", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    api: APISettings = Field(default_factory=APISettings)
    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the singleton settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment"""
    global _settings
    _settings = Settings()
    return _settings


# Convenience functions for common settings
def is_development() -> bool:
    """Check if running in development"""
    return get_settings().environment == Environment.DEVELOPMENT


def is_production() -> bool:
    """Check if running in production"""
    return get_settings().environment == Environment.PRODUCTION


def is_debug() -> bool:
    """Check if debug mode is enabled"""
    return get_settings().debug


if __name__ == "__main__":
    print("Testing Configuration Management...")

    settings = get_settings()
    print(f"Environment: {settings.environment}")
    print(f"Database URL: {settings.database.url}")
    print(f"API Port: {settings.api.port}")
    print(f"Debug: {settings.debug}")

    print("Configuration Management test complete!")
