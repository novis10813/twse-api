"""TWSE API Configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TWSE_")

    # TWSE request settings
    request_timeout: float = 30.0
    max_retries: int = 3

    # Database settings
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "core-postgres"
    postgres_port: int = 5432
    postgres_db: str = "twse_db"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
