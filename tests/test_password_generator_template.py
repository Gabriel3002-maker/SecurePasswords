import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "web-app" / "backend" / "app" / "templates" / "passwords.html"


class PasswordGeneratorTemplateTests(unittest.TestCase):
    def test_generate_password_request_includes_csrf_header(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        start = content.index("async function generatePassword()")
        end = content.index("function useGeneratedPassword()")
        snippet = content[start:end]

        self.assertIn("X-CSRF-Token", snippet)
        self.assertIn("getCSRFToken()", snippet)


if __name__ == "__main__":
    unittest.main()
