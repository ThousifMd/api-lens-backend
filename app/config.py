from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    MASTER_ENCRYPTION_KEY: str = ""
    ADMIN_API_KEY: str
    API_KEY_SALT: str = ""

    # Supabase
    SUPABASE_SERVICE_KEY: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_POSTGRES_URL: str = ""

    # API Settings
    API_PREFIX: str = "/api/v1"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60
    RATE_LIMIT_DEFAULT: int = 100
    COST_QUOTA_DEFAULT: float = 1000.0

    # App Info
    APP_NAME: str = "API Lens"
    VERSION: str = "0.1.0"
    
    # CORS Configuration
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000", "*"]

    # AI API Keys
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    ANTHROPIC_API_KEY: str

    # Optional Postgres direct URL
    #POSTGRES_DB_URL: str

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
