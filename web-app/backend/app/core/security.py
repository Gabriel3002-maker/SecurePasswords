from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import get_settings
import re

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def validate_password_requirements(password: str) -> tuple[bool, str]:
    """Validar que la contraseña sea suficientemente segura."""
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return False, "La contraseña debe incluir al menos una letra mayúscula."
    if not re.search(r"[a-z]", password):
        return False, "La contraseña debe incluir al menos una letra minúscula."
    if not re.search(r"\d", password):
        return False, "La contraseña debe incluir al menos un número."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "La contraseña debe incluir al menos un carácter especial."
    return True, "Contraseña fuerte y segura."


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash de contraseña"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crear JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def decode_token(token: str):
    """Decodificar JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None
