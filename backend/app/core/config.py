from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PetVerse API"
    app_env: str = "development"
    database_url: str = "sqlite:///./petverse.db"
    jwt_secret: str = "development-only-change-this-secret"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173"
    frontend_url: str = "http://localhost:5173"
    google_client_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@petverse.local"
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = 10
    ai_api_key: str | None = None
    ai_api_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
