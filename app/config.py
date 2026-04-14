from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "HUPX Price API"
    DEBUG_MODE: bool = True
    CACHE_TIMEOUT: int = 3600  # Refresh data every hour (3600 seconds)
    SCRAPER_NAME: str = "hupx"
    ENERGY_DEVICE_IP: str = "192.168.1.100"  # Local network IP
    ENERGY_DEVICE_TAILSCALE_IP: str = "100.116.216.29"  # Tailscale IP (optional, will try if local fails)
    USE_TAILSCALE_FIRST: bool = True  # Set to True to try Tailscale IP first (recommended for remote access)

    class Config:
        env_file = ".env"

settings = Settings()