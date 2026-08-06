import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(APP))

# Fake config para usar SQLite en memoria sin depender del .env local
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
sys.modules.setdefault("config", _fake_config)

from database import engine, SessionLocal
import models.models as m
import services.setup_service as ss
import core.telegram as tg
import api.recovery as rec
from api.recovery import RecoveryConfirm
from fastapi import HTTPException


class TestSetupRecovery(unittest.TestCase):

    def setUp(self):
        m.Base.metadata.drop_all(bind=engine)
        m.Base.metadata.create_all(bind=engine)
        # Limpiar variables de entorno de Telegram para aislamiento
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        # Mockear hashing bcrypt (roto en el python del host, no en el contenedor)
        ss.get_password_hash = lambda p: "H:" + p
        rec.get_password_hash = lambda p: "H:" + p
        rec.verify_password = lambda plain, hashed: hashed == "H:" + plain
        tg.send_message = lambda *a, **k: False

    def _get_setting(self, key):
        db = SessionLocal()
        try:
            row = db.query(m.SystemSetting).filter(m.SystemSetting.key == key).first()
            return row.value if row else None
        finally:
            db.close()

    def test_setup_stores_master_password_hash_and_telegram_token(self):
        ss.run_setup(
            db_name="passwords.db",
            admin_name="Admin",
            admin_email="admin@test.com",
            admin_password="StrongPass1!",
            master_password="MasterPass1!",
            telegram_bot_token="tok:123",
        )
        self.assertEqual(self._get_setting("master_password_hash"), "H:MasterPass1!")
        self.assertEqual(self._get_setting("telegram_bot_token"), "tok:123")

        db = SessionLocal()
        try:
            admin = db.query(m.User).filter(m.User.email == "admin@test.com").first()
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, m.UserRole.ADMIN)
        finally:
            db.close()

    def test_setup_requires_strong_master_password(self):
        with self.assertRaises(ValueError):
            ss.run_setup(
                db_name="passwords.db",
                admin_name="Admin",
                admin_email="admin@test.com",
                admin_password="StrongPass1!",
                master_password="weak",
            )

    def test_send_message_returns_false_without_token_or_chat(self):
        self.assertFalse(tg.send_message("hola"))

    def test_recovery_flow_sends_code_and_resets_master_password(self):
        # Vincular chat y definir maestra previa
        db = SessionLocal()
        db.add(m.SystemSetting(key="master_password_hash", value="H:old"))
        db.add(m.SystemSetting(key="telegram_chat_id", value="123456"))
        db.commit()
        db.close()

        rec._generate_code = lambda: "ABC123"
        sent = []
        tg.send_message = lambda text, chat_id=None: sent.append((text, chat_id)) or True

        result = rec.request_recovery({})
        self.assertEqual(result["message"], "Código enviado a tu chat de Telegram.")
        self.assertTrue(any("ABC123" in text for text, _ in sent))

        result2 = rec.confirm_recovery(SimpleNamespace(client=None), RecoveryConfirm(code="ABC123", new_master_password="NewMaster1!"))
        self.assertEqual(result2["message"], "Contraseña maestra restablecida correctamente.")
        self.assertEqual(self._get_setting("master_password_hash"), "H:NewMaster1!")

        db = SessionLocal()
        try:
            codes = db.query(m.RecoveryCode).all()
            self.assertEqual(len(codes), 1)
            self.assertIsNotNone(codes[0].used_at)
        finally:
            db.close()

    def test_recovery_rejects_invalid_code(self):
        db = SessionLocal()
        db.add(m.SystemSetting(key="master_password_hash", value="H:old"))
        db.add(m.SystemSetting(key="telegram_chat_id", value="123456"))
        db.commit()
        db.close()

        tg.send_message = lambda *a, **k: True
        with self.assertRaises(HTTPException) as ctx:
            rec.confirm_recovery(SimpleNamespace(client=None), RecoveryConfirm(code="ZZZZZZ", new_master_password="NewMaster1!"))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self._get_setting("master_password_hash"), "H:old")

    def test_recovery_request_fails_when_telegram_not_linked(self):
        tg.get_chat_id = lambda: None
        with self.assertRaises(HTTPException) as ctx:
            rec.request_recovery({})
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
