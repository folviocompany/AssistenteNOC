from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    llm_timeout_seconds: float = Field(default=30, gt=0)
    llm_max_tokens: int = Field(default=1500, gt=0)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_reasoning_enabled: bool | None = None
    max_text_length: int = Field(default=6000, gt=0)
    database_url: str = "sqlite:///./noc_ai.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
