from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
from typing import List, Optional

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"  # Allow extra fields from environment
    )
    
    # Core Application Settings
    APP_NAME: str = "API Lens Backend"
    APP_VERSION: str = "1.0.0"
    VERSION: str = "1.0.0"  # Keep for backward compatibility
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    # Security Settings
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MASTER_ENCRYPTION_KEY: str = ""
    ADMIN_API_KEY: str = ""
    API_KEY_SALT: str = ""
    
    # Request Size Limits
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024   # 50MB
    REQUEST_TIMEOUT: int = 30  # seconds
    
    # Security Headers
    SECURITY_HEADERS_ENABLED: bool = True
    SECURITY_HSTS_ENABLED: bool = True
    SECURITY_HSTS_MAX_AGE: int = 31536000  # 1 year
    SECURITY_FRAME_OPTIONS: str = "DENY"
    SECURITY_CONTENT_TYPE_NOSNIFF: bool = True
    SECURITY_XSS_PROTECTION: bool = True
    CSP_REPORT_URI: Optional[str] = None

    # Database Configuration
    DATABASE_URL: str
    ASYNC_DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    # Supabase (legacy support)
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_POSTGRES_URL: str = ""

    # Rate Limiting (for future implementation)
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60     # Legacy
    RATE_LIMIT_DEFAULT: int = 100   # Legacy
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 100
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_ANALYTICS_PER_MINUTE: int = 50
    RATE_LIMIT_PROXY_PER_MINUTE: int = 1000
    RATE_LIMIT_BURST_MULTIPLIER: int = 2

    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # External Service API Keys
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Monitoring & Observability
    METRICS_ENABLED: bool = True
    HEALTH_CHECK_ENABLED: bool = True
    HEALTH_CHECK_PATH: str = "/health"
    SENTRY_DSN: str = ""
    APM_ENABLED: bool = False
    
    # APM Configuration
    APM_PROVIDER: str = "none"  # Options: none, newrelic, datadog, elastic, sentry
    NEWRELIC_LICENSE_KEY: Optional[str] = None
    NEWRELIC_CONFIG_FILE: Optional[str] = None
    ELASTIC_APM_SERVER_URL: str = "http://localhost:8200"
    ELASTIC_APM_SECRET_TOKEN: Optional[str] = None
    ELASTIC_APM_SAMPLE_RATE: float = 0.1
    DATADOG_API_KEY: Optional[str] = None
    DATADOG_APP_KEY: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1
    
    # Distributed Tracing
    TRACING_ENABLED: bool = True
    TRACING_EXPORTER: str = "none"  # Options: none, otlp, jaeger, zipkin
    OTLP_ENDPOINT: str = "localhost:4317"
    OTLP_HEADERS: dict = {}
    JAEGER_AGENT_HOST: str = "localhost"
    JAEGER_AGENT_PORT: int = 6831
    JAEGER_COLLECTOR_ENDPOINT: Optional[str] = None
    ZIPKIN_ENDPOINT: str = "http://localhost:9411/api/v2/spans"

    # Logging Configuration
    LOG_FORMAT: str = "json"
    LOG_STRUCTURED: bool = True
    LOG_INCLUDE_TIMESTAMP: bool = True
    LOG_INCLUDE_LEVEL: bool = True
    LOG_INCLUDE_LOGGER_NAME: bool = True
    LOG_INCLUDE_PROCESS_ID: bool = True

    # Cache Configuration
    CACHE_ENABLED: bool = True
    CACHE_TTL_DEFAULT: int = 300
    CACHE_TTL_AUTH: int = 3600
    CACHE_TTL_PRICING: int = 1800
    CACHE_TTL_ANALYTICS: int = 600
    CACHE_PREFIX: str = "api_lens"
    CACHE_COMPRESSION: bool = True

    # Security Headers
    SECURITY_HEADERS_ENABLED: bool = True
    SECURITY_HSTS_ENABLED: bool = True
    SECURITY_HSTS_MAX_AGE: int = 31536000
    SECURITY_CSP_ENABLED: bool = True
    SECURITY_FRAME_OPTIONS: str = "DENY"
    SECURITY_CONTENT_TYPE_NOSNIFF: bool = True
    SECURITY_XSS_PROTECTION: bool = True

    # API Documentation
    DOCS_ENABLED: bool = True
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"

    # Feature Flags
    FEATURE_ANALYTICS_V2: bool = True
    FEATURE_ADVANCED_MONITORING: bool = True
    FEATURE_REAL_TIME_UPDATES: bool = True
    FEATURE_COST_ALERTS: bool = True
    FEATURE_ANOMALY_DETECTION: bool = True
    FEATURE_EXPORT_REPORTS: bool = True

    # Timezone & Location
    DEFAULT_TIMEZONE: str = "UTC"
    TIMEZONE_DETECTION_ENABLED: bool = True
    GEOLOCATION_ENABLED: bool = True
    GEOLOCATION_PROVIDER: str = "ipapi"

    # Production Settings
    WORKERS: int = 4
    WORKER_CLASS: str = "uvicorn.workers.UvicornWorker"
    TIMEOUT: int = 30
    KEEPALIVE: int = 2
    GRACEFUL_TIMEOUT: int = 120

    # Legacy Settings (for backward compatibility)
    COST_QUOTA_DEFAULT: float = 1000.0

@lru_cache()
def get_settings() -> Settings:
    return Settings()
