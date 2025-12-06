"""Application settings and configuration management.

This module provides the Settings class that loads and manages application
configuration from environment variables, including bot credentials, database
connection parameters, payment system settings, and external service endpoints.
"""

from typing import Any, Optional

from pydantic import Field, PostgresDsn
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
    db_port: int = Field(15432, alias="postgres_port")
    db_url: Optional[PostgresDsn] = None

    yookassa_api_key: str = Field("")
    yookassa_api_secret: str = Field("")
    yookassa_tax_system_code: int = Field(1)
    return_url: Optional[str] = Field(None)

    admin_tg_ids: Optional[list[int]] = Field(None)

    openrouter_token: Optional[str] = Field(None)
    openai_api_key: Optional[str] = Field(None)

    def model_post_init(self, context: Optional[Any]) -> None:
        """Construct the database URL from individual connection parameters.

        Builds a PostgreSQL DSN (Data Source Name) URL using asyncpg driver
        from the configured host, port, username, password, and database name
        if db_url is not already set. Prints the constructed database URL.

        Args:
            context: Optional context passed by Pydantic during model initialization.
        """
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


settings = Settings()