import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(ROOT))

from core.security import validate_password_requirements


class PasswordValidationTests(unittest.TestCase):
    def test_accepts_strong_password(self):
        is_valid, message = validate_password_requirements("Str0ng!Passw0rd")
        self.assertTrue(is_valid)
        self.assertIn("fuerte", message.lower())

    def test_rejects_weak_password(self):
        is_valid, message = validate_password_requirements("password")
        self.assertFalse(is_valid)
        self.assertIn("al menos", message.lower())


if __name__ == "__main__":
    unittest.main()
