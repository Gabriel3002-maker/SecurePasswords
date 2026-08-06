import sys
import time
import types
import unittest
import hashlib
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(APP))

# Config falsa con SQLite en memoria (igual que el resto de la suite)
_fake_config = types.ModuleType("config")
_fake_config.get_settings = lambda: SimpleNamespace(
    database_url="sqlite:///:memory:",
    secret_key="test-secret-key",
    algorithm="HS256",
    access_token_expire_minutes=30,
    encryption_key="test-encryption-key",
    app_name="test",
    debug=False,
)
sys.modules["config"] = _fake_config

import core.security as cs
import core.rate_limit as rl
import models.models as m
import api.auth as auth
import api.credentials as creds
import api.ssh as ssh_mod
import services.setup_service as ss
import services.auth_service as auth_service
from database import engine, SessionLocal
from core.encryption import encrypt_password
from core.security import create_access_token
from schemas.schemas import GeneratePasswordRequest, PermissionCreate, UserCreate
from fastapi import HTTPException


# ─── #14: hash de duplicados con HMAC ───────────────────────────
class DuplicateHashTests(unittest.TestCase):
    def test_hmac_is_deterministic_and_not_plain_sha256(self):
        h1 = cs.get_duplicate_hash("S3cret!")
        h2 = cs.get_duplicate_hash("S3cret!")
        h3 = cs.get_duplicate_hash("OtraPass!")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h1, hashlib.sha256(b"S3cret!").hexdigest())


# ─── #15: generador con secrets y clases garantizadas ───────────
class PasswordGeneratorTests(unittest.TestCase):
    def test_generates_password_with_all_requested_classes(self):
        req = GeneratePasswordRequest(length=12)
        res = creds.generate_password(req, current_user=SimpleNamespace(id="u1"))
        pw = res["password"]
        self.assertEqual(len(pw), 12)
        self.assertTrue(any(c.isupper() for c in pw))
        self.assertTrue(any(c.islower() for c in pw))
        self.assertTrue(any(c.isdigit() for c in pw))
        self.assertTrue(any(not c.isalnum() for c in pw))


# ─── #16: rate limit con expiración por email e IP ──────────────
class RateLimitTests(unittest.TestCase):
    def setUp(self):
        auth.email_limiter._memory.clear()
        auth.ip_limiter._memory.clear()

    def test_blocks_after_five_failures_per_email(self):
        for _ in range(5):
            auth.email_limiter.record("v@test.com", False)
        with self.assertRaises(HTTPException) as ctx:
            auth._check_rate_limit("v@test.com", "9.9.9.9")
        self.assertEqual(ctx.exception.status_code, 429)

    def test_block_expires_after_window(self):
        for _ in range(5):
            auth.email_limiter.record("v@test.com", False)
        auth.email_limiter._memory["v@test.com"]["last_attempt"] = time.time() - 16 * 60
        auth._check_rate_limit("v@test.com", "9.9.9.9")  # no debe lanzar
        self.assertNotIn("v@test.com", auth.email_limiter._memory)

    def test_successful_login_clears_counter(self):
        auth.email_limiter.record("ok@test.com", False)
        auth.email_limiter.record("ok@test.com", True)
        self.assertNotIn("ok@test.com", auth.email_limiter._memory)

    def test_blocks_ip_to_prevent_third_party_lockout(self):
        for _ in range(20):
            auth.ip_limiter.record("7.7.7.7", False)
        with self.assertRaises(HTTPException) as ctx:
            auth._check_rate_limit("ajeno@test.com", "7.7.7.7")
        self.assertEqual(ctx.exception.status_code, 429)


# ─── RateLimiter compartido (Redis con fallback en memoria) ─────
class RateLimiterUnitTests(unittest.TestCase):
    def setUp(self):
        self.limiter = rl.RateLimiter("test", 3, lockout_seconds=900)

    def test_allows_below_max_and_blocks_above(self):
        self.assertEqual(self.limiter.remaining_lockout("k"), 0)
        for _ in range(2):
            self.limiter.record("k", False)
        self.assertEqual(self.limiter.remaining_lockout("k"), 0)
        self.limiter.record("k", False)
        self.assertGreater(self.limiter.remaining_lockout("k"), 0)

    def test_window_expires_and_counter_is_cleared(self):
        for _ in range(3):
            self.limiter.record("k", False)
        self.limiter._memory["k"]["last_attempt"] = time.time() - 16 * 60
        self.assertEqual(self.limiter.remaining_lockout("k"), 0)
        self.assertNotIn("k", self.limiter._memory)

    def test_success_resets_counter(self):
        for _ in range(2):
            self.limiter.record("k", False)
        self.limiter.record("k", True)
        self.assertEqual(self.limiter.remaining_lockout("k"), 0)

    def test_keys_are_scoped_by_prefix(self):
        a = rl.RateLimiter("a", 1, 900)
        b = rl.RateLimiter("b", 1, 900)
        a.record("k", False)
        self.assertEqual(b.remaining_lockout("k"), 0)


# ─── #9, #10, #11, #12, #13: dependientes de BD ─────────────────
class SecurityFixesDBTests(unittest.TestCase):
    def setUp(self):
        m.Base.metadata.drop_all(bind=engine)
        m.Base.metadata.create_all(bind=engine)
        # bcrypt/passlib roto en el host (ver test_setup_recovery)
        self._orig_hash = cs.get_password_hash
        cs.get_password_hash = lambda p: "H:" + p
        ss.get_password_hash = lambda p: "H:" + p
        auth_service.get_password_hash = lambda p: "H:" + p

        self.db = SessionLocal()
        self.org_a = m.Organization(name="OrgA"); self.db.add(self.org_a); self.db.flush()
        self.org_b = m.Organization(name="OrgB"); self.db.add(self.org_b); self.db.flush()
        self.admin_a = m.User(
            email="admina@test.com", password_hash="x", role=m.UserRole.ADMIN,
            organization_id=self.org_a.id, is_active=True,
        )
        self.admin_b = m.User(
            email="adminb@test.com", password_hash="x", role=m.UserRole.ADMIN,
            organization_id=self.org_b.id, is_active=True,
        )
        self.db.add_all([self.admin_a, self.admin_b]); self.db.flush()
        self.cred_a = m.Credential(
            host="a.srv", username="root", password_encrypted=encrypt_password("pwA"),
            created_by=self.admin_a.id, organization_id=self.org_a.id,
        )
        self.cred_b = m.Credential(
            host="b.srv", username="root", password_encrypted=encrypt_password("pwB"),
            created_by=self.admin_b.id, organization_id=self.org_b.id,
        )
        self.db.add_all([self.cred_a, self.cred_b]); self.db.commit()

    def tearDown(self):
        cs.get_password_hash = self._orig_hash
        auth_service.get_password_hash = self._orig_hash
        self.db.close()

    # #9
    def test_register_forces_user_role_and_admin_org(self):
        data = UserCreate(
            email="nuevo@test.com", password="Str0ng1!a", full_name="Nuevo",
            role=m.UserRole.ADMIN, organization_id=self.org_b.id,
        )
        user = auth.register(
            user_data=data,
            current_admin=self.admin_a,
            db=self.db,
        )
        self.assertEqual(user.role, m.UserRole.USER)
        self.assertEqual(user.organization_id, self.org_a.id)

    # #12
    def test_setup_refuses_when_already_configured(self):
        with self.assertRaises(ValueError) as ctx:
            ss.run_setup(
                db_name="x", admin_name="A", admin_email="a@test.com",
                admin_password="StrongPass1!",
            )
        self.assertIn("ya está configurado", str(ctx.exception))

    # #10
    def test_permissions_reject_credential_from_other_org(self):
        with self.assertRaises(HTTPException) as ctx:
            creds.grant_permission(
                self.cred_b.id, PermissionCreate(user_id=self.admin_a.id),
                current_user=self.admin_a, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_permissions_list_rejects_other_org_credential(self):
        with self.assertRaises(HTTPException) as ctx:
            creds.list_permissions(self.cred_b.id, current_user=self.admin_a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_permissions_still_work_inside_own_org(self):
        creds.grant_permission(
            self.cred_a.id, PermissionCreate(user_id=self.admin_a.id),
            current_user=self.admin_a, db=self.db,
        )

    # #11
    def test_audit_only_shows_own_organization(self):
        creds._log_audit(self.db, self.admin_a.id, "created", "credential", self.cred_a.id, {"host": "a"}, "1.1.1.1")
        creds._log_audit(self.db, self.admin_b.id, "created", "credential", self.cred_b.id, {"host": "b"}, "2.2.2.2")
        self.db.commit()

        logs = creds.global_audit(current_user=self.admin_a, db=self.db)
        resource_ids = {l.resource_id for l in logs}
        self.assertIn(self.cred_a.id, resource_ids)
        self.assertNotIn(self.cred_b.id, resource_ids)

    # #13
    def test_ws_auth_accepts_valid_cookie(self):
        token = create_access_token({"sub": str(self.admin_a.id)})
        user = ssh_mod._get_ws_user(_FakeWS({"access_token": f"Bearer {token}"}))
        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.admin_a.id)

    def test_ws_auth_rejects_missing_or_invalid_token(self):
        self.assertIsNone(ssh_mod._get_ws_user(_FakeWS({})))
        self.assertIsNone(ssh_mod._get_ws_user(_FakeWS({"access_token": "Bearer invalido"})))

    def test_ws_auth_rejects_inactive_user(self):
        inactive = m.User(
            email="ina@test.com", password_hash="x", role=m.UserRole.USER,
            organization_id=self.org_a.id, is_active=False,
        )
        self.db.add(inactive); self.db.flush()
        token = create_access_token({"sub": str(inactive.id)})
        self.assertIsNone(ssh_mod._get_ws_user(_FakeWS({"access_token": f"Bearer {token}"})))


class _FakeWS:
    def __init__(self, cookies):
        self.cookies = cookies


if __name__ == "__main__":
    unittest.main()
