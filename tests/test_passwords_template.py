import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "web-app" / "backend" / "app" / "templates" / "passwords.html"


class PasswordsTemplateTests(unittest.TestCase):
    def test_folder_counts_use_total_and_folders_fields(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        start = content.index("async function loadFolderCounts()")
        end = content.index("function filterByFolder")
        snippet = content[start:end]

        self.assertIn("data.total", snippet)
        self.assertIn("data.folders", snippet)
        self.assertNotIn("Object.values(counts)", snippet)

    def test_share_modal_loads_users_lazily_and_handles_empty_list(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("async function loadShareUsers()", content)
        self.assertIn("passwords.no_users_to_share", content)
        self.assertIn("function showShareModal", content)

    def test_assign_permission_guards_empty_users_list(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        start = content.index("async function assignPermission()")
        end = content.index("function connectSSH")
        snippet = content[start:end]

        self.assertIn("!allUsers.length", snippet)
        self.assertIn("passwords.no_users_to_share", snippet)


if __name__ == "__main__":
    unittest.main()
