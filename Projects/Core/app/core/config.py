from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "Conlon Hub"
    environment: str = "development"
    version: str = "0.1.0"
    ai_history_message_limit: int = Field(
        default=40, ge=2, le=200, multiple_of=2
    )
    ai_requests_per_minute: int = Field(default=10, ge=1, le=120)

settings = Settings()
