from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "HUPX Price API"
    DEBUG_MODE: bool = True
    CACHE_TIMEOUT: int = 3600  # Refresh data every hour (3600 seconds)

    class Config:
        env_file = ".env"

settings = Settings()