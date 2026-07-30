import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(ROOT))

from core.security import get_password_hash
from services.auth_service import authenticate_user


class AuthServiceTests(unittest.TestCase):
    def test_authenticates_active_user_with_valid_password(self):
        password = "Str0ng!Passw0rd"
        user = SimpleNamespace(password_hash=get_password_hash(password), is_active=True)

        is_valid, message = authenticate_user(user, password)

        self.assertTrue(is_valid)
        self.assertIsNone(message)

    def test_rejects_inactive_user(self):
        password = "Str0ng!Passw0rd"
        user = SimpleNamespace(password_hash=get_password_hash(password), is_active=False)

        is_valid, message = authenticate_user(user, password)

        self.assertFalse(is_valid)
        self.assertEqual(message, "Usuario inactivo")


if __name__ == "__main__":
    unittest.main()
