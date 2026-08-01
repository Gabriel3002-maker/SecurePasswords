from cryptography.fernet import Fernet, InvalidToken
from config import get_settings
import base64
import hashlib

settings = get_settings()

def _derive_fernet_key(raw_key: str) -> bytes:
    """Derivar una clave Fernet válida (32 bytes URL-safe base64) usando SHA-256."""
    digest = hashlib.sha256(raw_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def get_cipher() -> Fernet:
    key = settings.encryption_key.encode()
    if not settings.encryption_key or settings.encryption_key == "setup_mode_key":
        raise RuntimeError("ENCRYPTION_KEY no configurada")
    try:
        return Fernet(key)
    except (ValueError, InvalidToken):
        derived = _derive_fernet_key(settings.encryption_key)
        return Fernet(derived)

def encrypt_password(password: str) -> str:
    """Encriptar contraseña"""
    cipher = get_cipher()
    encrypted = cipher.encrypt(password.encode())
    return encrypted.decode()

def decrypt_password(encrypted_password: str) -> str:
    """Desencriptar contraseña"""
    cipher = get_cipher()
    decrypted = cipher.decrypt(encrypted_password.encode())
    return decrypted.decode()
