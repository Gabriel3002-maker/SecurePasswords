import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import bcrypt

class PasswordEncryption:
    def __init__(self, master_password: str, salt: bytes = None):
        self.master_password = master_password.encode()
        if salt is None:
            salt = bcrypt.gensalt()
        self.salt = salt
        self.key = self._derive_key()

    def _derive_key(self) -> bytes:
        """Derive encryption key from master password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.master_password))

    def encrypt(self, data: str) -> str:
        """Encrypt data using Fernet symmetric encryption"""
        fernet = Fernet(self.key)
        return fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet symmetric encryption"""
        fernet = Fernet(self.key)
        return fernet.decrypt(encrypted_data.encode()).decode()

    def verify_master_password(self, input_password: str) -> bool:
        """Verify if the input password matches the master password"""
        return bcrypt.checkpw(input_password.encode(), self.salt)

    def get_salt(self) -> bytes:
        """Get the salt used for key derivation"""
        return self.salt

    @staticmethod
    def generate_salt() -> bytes:
        """Generate a new random salt"""
        return bcrypt.gensalt()

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()