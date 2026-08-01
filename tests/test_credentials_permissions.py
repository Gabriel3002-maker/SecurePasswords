import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(APP))

# El .env local contiene ALLOWED_ORIGINS/DEBUG, claves que el Settings de
# pydantic-settings no acepta como extra en entornos de test. Usamos un
# módulo config simulado para importar la app sin tocar la configuración real.
import types

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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.models import Organization, User, UserRole, Credential, CredentialPermission
from core.encryption import encrypt_password
from api.credentials import _get_user_permissions


class CredentialPermissionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.org = Organization(name="TestOrg")
        self.db.add(self.org)
        self.db.flush()

        self.admin = User(
            email="admin@test.com", password_hash="x", full_name="Admin",
            role=UserRole.ADMIN, organization_id=self.org.id, is_active=True,
        )
        self.shared = User(
            email="user@test.com", password_hash="x", full_name="User",
            role=UserRole.USER, organization_id=self.org.id, is_active=True,
        )
        self.other = User(
            email="other@test.com", password_hash="x", full_name="Other",
            role=UserRole.USER, organization_id=self.org.id, is_active=True,
        )
        self.db.add_all([self.admin, self.shared, self.other])
        self.db.flush()

        self.cred = Credential(
            host="server.example.com", username="root",
            password_encrypted=encrypt_password("S3cret!"),
            created_by=self.admin.id, organization_id=self.org.id,
        )
        self.db.add(self.cred)
        self.db.flush()

        perm = CredentialPermission(
            credential_id=self.cred.id, user_id=self.shared.id,
            can_view=True, can_edit=True, can_delete=False, can_connect_ssh=True,
            granted_by=self.admin.id,
        )
        self.db.add(perm)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_admin_gets_full_permissions(self):
        perms = _get_user_permissions(self.admin, self.cred, self.db)
        self.assertEqual(
            perms,
            {"can_view": True, "can_edit": True, "can_delete": True, "can_connect_ssh": True},
        )

    def test_owner_gets_full_permissions(self):
        owner = User(
            email="owner@test.com", password_hash="x", full_name="Owner",
            role=UserRole.USER, organization_id=self.org.id, is_active=True,
        )
        self.db.add(owner)
        self.db.flush()
        own_cred = Credential(
            host="own.example.com", username="root",
            password_encrypted=encrypt_password("S3cret!"),
            created_by=owner.id, organization_id=self.org.id,
        )
        self.db.add(own_cred)
        self.db.commit()
        perms = _get_user_permissions(owner, own_cred, self.db)
        self.assertTrue(all(perms.values()))

    def test_shared_user_gets_granted_permissions(self):
        perms = _get_user_permissions(self.shared, self.cred, self.db)
        self.assertEqual(
            perms,
            {"can_view": True, "can_edit": True, "can_delete": False, "can_connect_ssh": True},
        )

    def test_view_only_user_does_not_get_edit_delete_ssh(self):
        viewer = User(
            email="viewer@test.com", password_hash="x", full_name="Viewer",
            role=UserRole.USER, organization_id=self.org.id, is_active=True,
        )
        self.db.add(viewer)
        self.db.flush()
        perm = CredentialPermission(
            credential_id=self.cred.id, user_id=viewer.id,
            can_view=True, can_edit=False, can_delete=False, can_connect_ssh=False,
            granted_by=self.admin.id,
        )
        self.db.add(perm)
        self.db.commit()
        perms = _get_user_permissions(viewer, self.cred, self.db)
        self.assertEqual(
            perms,
            {"can_view": True, "can_edit": False, "can_delete": False, "can_connect_ssh": False},
        )

    def test_user_without_permission_gets_none(self):
        perms = _get_user_permissions(self.other, self.cred, self.db)
        self.assertEqual(
            perms,
            {"can_view": False, "can_edit": False, "can_delete": False, "can_connect_ssh": False},
        )


if __name__ == "__main__":
    unittest.main()
