"""
Configuration management using pydantic-settings.
"""

import os
import logging
from typing import List, Union
from pydantic import field_validator, ValidationInfo, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("diffguard.config")

DEFAULT_DEV_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


class Settings(BaseSettings):
    APP_NAME: str = "DiffGuard"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    # Gemini API settings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_REQUEST_TIMEOUT_MS: int = 25_000  # 25s upstream timeout in milliseconds (google-genai HttpOptions unit)
    INVESTIGATION_DEADLINE_SECONDS: float = 60.0  # 60s total investigation budget
    
    # Guardrails and constraints
    MAX_DIFF_SIZE_BYTES: int = 1_048_576  # 1 MB limit for practical evaluation
    MAX_FILES_PER_DIFF: int = 50
    REQUEST_TIMEOUT_SECONDS: int = 60
    
    # CORS: Explicitly allowed origins. Wildcards ("*") are strictly prohibited.
    # Accepts either CORS_ORIGINS or DIFFGUARD_CORS_ORIGINS from environment.
    CORS_ORIGINS: Union[List[str], str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("CORS_ORIGINS", "DIFFGUARD_CORS_ORIGINS")
    )
    CORS_ORIGIN_REGEX: str = r"^https://.*\.vercel\.app$|^https://.*\.netlify\.app$"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]], info: ValidationInfo) -> List[str]:
        app_env = str((info.data.get("APP_ENV") if info and info.data else None) or os.getenv("APP_ENV", "development")).strip().lower()
        is_production = (app_env == "production")

        if isinstance(v, str):
            raw_origins = [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, tuple)):
            raw_origins = [str(item).strip() for item in v if str(item).strip()]
        else:
            raw_origins = []

        cleaned: List[str] = []
        for o in raw_origins:
            if o == "*":
                continue
            # Strip whitespace and trailing slashes for clean origin matching
            norm = o.rstrip("/")
            if not norm:
                continue
            # In production, do not inherit or allow localhost/127.0.0.1 development origins
            if is_production and any(dev in norm for dev in ("localhost", "127.0.0.1")):
                logger.warning(f"Excluding development origin '{norm}' from production CORS allowlist.")
                continue
            if norm not in cleaned:
                cleaned.append(norm)

        # In non-production (development, test), include default local dev origins if not present
        if not is_production:
            for dev_origin in DEFAULT_DEV_ORIGINS:
                norm_dev = dev_origin.rstrip("/")
                if norm_dev not in cleaned:
                    cleaned.append(norm_dev)
        elif not cleaned:
            logger.warning("Production CORS configuration has no allowed origins; all cross-origin requests will be rejected.")

        return cleaned

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
