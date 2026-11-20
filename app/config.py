from functools import lru_cache
import secrets
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "UbuntuBiz Backend"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"

    # Security & JWT
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    BCRYPT_ROUNDS: int = 12
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database & Storage
    # Default is SQLite for local file-based testing; in production/docker use PostgreSQL
    DATABASE_URL: str = "sqlite:///./ubuntubiz.db"
    DB_ECHO: bool = False

    # Redis & Background Tasks
    REDIS_URL: str = "redis://localhost:6379/0"

    # Blockchain (Avalanche Fuji C-Chain)
    AVAX_FUJI_RPC_URL: str = "https://api.avax-test.network/ext/bc/C/rpc"
    AVAX_FUJI_CHAIN_ID: int = 43113
    AVAX_FUJI_HEX_CHAIN_ID: str = "0xa869"
    UBUNTUBIZ_CONTRACT_ADDRESS: str = "0xE019a407a590C4348ea24c92Dc5Ac6C642e22f91"

    # Gemini AI
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    MAX_AGENT_LOOPS: int = 5
    ENABLE_TOOL_ALLOWLIST_ENFORCEMENT: bool = True

    # WhatsApp & Webhooks
    WHATSAPP_VERIFY_TOKEN: Optional[str] = None
    WHATSAPP_API_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_APP_SECRET: Optional[str] = None

    # Regional Settings
    DEFAULT_CURRENCY: str = "ZAR"
    TIMEZONE: str = "Africa/Johannesburg"
    CENTS_PER_ZAR: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_runtime_security(self):
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")

        if self.ENVIRONMENT.lower() in {"production", "prod"}:
            if "SECRET_KEY" not in self.model_fields_set:
                raise ValueError("SECRET_KEY must be configured in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be disabled in production")

        return self

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
