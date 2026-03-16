from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str = "Spec sheet Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ==================================================================
    # DATABASE CONFIGURATION
    # ==================================================================
    DATABASE_URL: str = ""

    # ==================================================================
    # REDIS CONFIGURATION
    # ==================================================================
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_CACHE_TTL: int = 86400

    # ==================================================================
    # CELERY CONFIGURATION
    # ==================================================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # ==================================================================
    # EXTERNAL API CONFIGURATION
    # ==================================================================
    # Keep Serper because your normal source-discovery flow still uses it,
    # but it should no longer be mandatory for PASS 4 grounded fallback.
    SERPER_API_KEY: str = ""  # Loaded from .env
    SERPER_BASE_URL: str = "https://google.serper.dev/search"
    SERPER_QUOTA_ENDPOINT: str = "https://google.serper.dev/account"
    SERPER_MAX_RESULTS: int = 5
    SERPER_CREDIT_WARNING_THRESHOLD: int = 100  # Warn when < 100 credits remaining
    SERPER_CREDIT_CRITICAL_THRESHOLD: int = 10  # Critical when < 10 credits remaining

    GEMINI_API_KEY: str = ""  # Loaded from .env

    # ==================================================================
    # AWS S3 CONFIGURATION
    # ==================================================================
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_ENDPOINT: str = ""
    AWS_S3_REGION: str = "sjc1"
    AWS_S3_BUCKET: str = "test1"

    # Primary PDF extraction model - UPGRADED TO PRO FOR BETTER TABLE PARSING
    # Pro: Better at understanding complex tables, STC conditions, spec sheets
    # Trade: 15-20s per item (but 50 workers handle it = still fast overall)
    GEMINI_MODEL: str = "gemini-2.5-pro"

    # Repair / verification PDF passes
    GEMINI_REPAIR_MODEL: str = "gemini-2.5-pro"

    # Additional fallback PDF-capable models
    GEMINI_FALLBACK_MODELS: str = "gemini-1.5-flash"

    # PASS 2/3 search/verification model
    # Using 2.0 Flash instead of 3.1 Pro to avoid quota limits (25 req/min)
    # 2.0 Flash has higher quota and is faster (3-4s vs 15-20s per item)
    GEMINI_INTERNET_SEARCH_MODEL: str = "gemini-2.0-flash"

    # Generation settings
    GEMINI_MAX_TOKENS: int = 4096
    GEMINI_TEMPERATURE: float = 0.0

    # Optional feature flags
    ENABLE_SERPER_SOURCE_SEARCH: bool = True
    ENABLE_GROUNDED_WEB_FALLBACK: bool = True

    # ==================================================================
    # APPLICATION CONFIGURATION
    # ==================================================================
    TARGET_COUNTRY: str = "US"
    MIN_TRUST_SCORE: int = 50
    MIN_MATCH_SCORE: float = 80.0
    MIN_CONFIDENCE_SCORE: float = 0.60

    # ==================================================================
    # VALIDATION THRESHOLDS
    # ==================================================================
    VALIDATION_PASS_THRESHOLD: float = 0.70
    VALIDATION_PARTIAL_THRESHOLD: float = 0.40
    VALIDATION_REJECT_THRESHOLD: float = 0.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "DATABASE_URL is required. "
                "Please set it in .env file or as an environment variable. "
                "Format: postgresql://username:password@host:port/database"
            )
        return v

    @field_validator("GEMINI_API_KEY", mode="after")
    @classmethod
    def validate_gemini_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "GEMINI_API_KEY is required. "
                "Get it from: https://makersuite.google.com/app/apikey"
            )
        return v

    @field_validator("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_ENDPOINT", "AWS_S3_BUCKET", mode="after")
    @classmethod
    def validate_aws_config(cls, v: str, info) -> str:
        # AWS credentials are optional until S3 feature is used
        return v

    @field_validator("SERPER_API_KEY", mode="after")
    @classmethod
    def validate_serper_key(cls, v: str) -> str:
        """
        Serper is optional now.
        If you still use source discovery, leave ENABLE_SERPER_SOURCE_SEARCH=True
        and provide the key.
        """
        return v or ""


settings = Settings()