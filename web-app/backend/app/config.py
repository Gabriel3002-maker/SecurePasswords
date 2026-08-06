from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    database_url: str = "sqlite:///./passwords.db"
    secret_key: str = "setup_mode_key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    encryption_key: str = "setup_mode_key"
    app_name: str = "Gestor de Contraseñas"
    debug: bool = False
    cookie_secure: bool = False
    redis_url: str = ""

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        env_file_encoding = "utf-8"
        # ALLOWED_ORIGINS / DEBUG se leen con os.getenv en main.py, no son campos de Settings
        extra = "ignore"

    def validate_post_setup(self) -> None:
        if self.secret_key in ("setup_mode_key", "your-secret-key-here-change-in-production", ""):
            raise RuntimeError("SECRET_KEY no está configurada correctamente. Ejecuta la configuración inicial.")
        if self.encryption_key in ("setup_mode_key", "your-encryption-key-here-change-in-production", ""):
            raise RuntimeError("ENCRYPTION_KEY no está configurada correctamente. Ejecuta la configuración inicial.")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
