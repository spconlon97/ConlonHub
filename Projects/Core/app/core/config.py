from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Conlon Hub"
    environment: str = "development"
    version: str = "0.1.0"

    class Config:
        env_file = ".env"


settings = Settings()