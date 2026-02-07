"""Application settings and configuration management.

This module provides the Settings class that loads and manages application
configuration from environment variables, including bot credentials, database
connection parameters, payment system settings, and external service endpoints.
"""
from functools import lru_cache, cached_property
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, PostgresDsn, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and configuration management.

    Loads and manages application configuration from environment variables,
    including bot credentials, database connection parameters, payment system
    settings, and external service endpoints. Automatically constructs the
    PostgreSQL database URL from individual connection parameters during
    model initialization.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = Field()

    db_name: str = Field("breathing_db", alias="postgres_db")
    db_user: str = Field("postgres", alias="postgres_user")
    db_password: str = Field("postgres", alias="postgres_password")
    db_host: str = Field("postgres", alias="postgres_host")
    db_port: int = Field(5432, alias="postgres_port")
    db_url: Optional[PostgresDsn] = None

    yookassa_api_key: str = Field("")
    yookassa_api_secret: str = Field("")
    yookassa_tax_system_code: int = Field(1)
    return_url: Optional[str] = Field(None)

    admin_tg_ids: Optional[list[int]] = Field(None)

    openrouter_token: Optional[str] = Field(None)
    openrouter_model: Optional[str] = Field("anthropic/claude-3.5-haiku")
    prompt_file: str = "prompt.txt"
    openai_api_key: Optional[str] = Field(None)

    def model_post_init(self, context: Optional[Any]) -> None:
        if not self.db_url:
            self.db_url = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                host=self.db_host,
                port=self.db_port,
                username=self.db_user,
                password=self.db_password,
                path=f"{self.db_name}",
            )
        print(self.db_url)

    @cached_property
    def openrouter_comment_prompt(self) -> str:
        """Свойство для загрузки промпта из файла"""
        path = Path(self.prompt_file)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "Ты эмпатичный ассистент. Ответь на комментарий пользователя кратко, по делу и поддерживающе."

settings = Settings()
