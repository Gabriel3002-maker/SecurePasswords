import sys
import unittest
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(ROOT))

# Config falsa con SQLite en memoria: este fichero corre primero en la suite y,
# si importa el config real, envenena los demás tests con la DATABASE_URL local.
_fake_config = types.ModuleType("config")
_fake_config.get_settings = lambda: SimpleNamespace(
    database_url="sqlite:///:memory:",
    secret_key="test",
    algorithm="HS256",
    access_token_expire_minutes=30,
    encryption_key="test",
    app_name="test",
    debug=False,
)
sys.modules["config"] = _fake_config

import core.security as cs
import services.auth_service as auth_service

# bcrypt/passlib está roto en el python del host (no en el contenedor), igual
# que documenta test_setup_recovery: usamos un hash simulado.
cs.get_password_hash = lambda p: "H:" + p
cs.verify_password = lambda plain, hashed: hashed == "H:" + plain
auth_service.verify_password = cs.verify_password

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
