from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./passwords.db"
    
    # Security
    secret_key: str = "setup_mode_key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Encryption
    encryption_key: str = "setup_mode_key"
    
    # App
    app_name: str = "Gestor de Contraseñas"
    debug: bool = False
    
    class Config:
        # Buscar .env en el directorio backend (un nivel arriba de app/)
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        env_file_encoding = 'utf-8'

@lru_cache()
def get_settings():
    return Settings()
