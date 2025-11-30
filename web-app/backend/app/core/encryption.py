from cryptography.fernet import Fernet
from config import get_settings
import base64

settings = get_settings()

def get_cipher():
    """Obtener cipher para encriptación"""
    # Asegurar que la key tenga el formato correcto
    key = settings.encryption_key.encode()
    # Si no es una key válida de Fernet, generarla
    try:
        return Fernet(key)
    except:
        # Generar key desde la configuración
        key = base64.urlsafe_b64encode(key.ljust(32)[:32])
        return Fernet(key)

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
