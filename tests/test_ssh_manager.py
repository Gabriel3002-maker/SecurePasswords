import os
import sys
import tempfile
import unittest
import asyncio
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(APP))

# Mismo enfoque que test_credentials_permissions: el .env local tiene claves
# extra (ALLOWED_ORIGINS/DEBUG) que pydantic-settings no acepta en este entorno.
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

import paramiko

import core.ssh_manager as sm
from core.ssh_manager import SSHManager, _get_known_hosts_path


class _FakeChannel:
    def __init__(self):
        self.timeout = None
        self.sent = []

    def settimeout(self, t):
        self.timeout = t

    def recv_ready(self):
        return False

    def recv(self, n):
        return b""

    @property
    def closed(self):
        return True

    def exit_status_ready(self):
        return True

    def send(self, data):
        self.sent.append(data)


class _FakeClient:
    def __init__(self):
        self.channel = _FakeChannel()
        self.closed = False

    def invoke_shell(self, term="xterm"):
        return self.channel

    def close(self):
        self.closed = True


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(text)

    async def receive_text(self):
        raise sm.WebSocketDisconnect(code=1000)


class _FakeWSAccept(_FakeWS):
    def __init__(self):
        super().__init__()
        self.accepted = False
        self.closed = None

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=None):
        self.closed = (code, reason)



class SSHManagerTests(unittest.TestCase):
    def test_known_hosts_path_is_absolute(self):
        self.assertTrue(os.path.isabs(_get_known_hosts_path()))

    def test_prepare_host_key_policy_creates_directory_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = sm.KNOWN_HOSTS_PATH
            sm.KNOWN_HOSTS_PATH = os.path.join(tmp, "nested", "dir", "known_hosts")
            try:
                client = paramiko.SSHClient()
                SSHManager._prepare_host_key_policy(client)
                self.assertTrue(os.path.isdir(os.path.dirname(sm.KNOWN_HOSTS_PATH)))
                self.assertTrue(os.path.isfile(sm.KNOWN_HOSTS_PATH))
            finally:
                sm.KNOWN_HOSTS_PATH = original

    def test_save_host_keys_succeeds_after_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = sm.KNOWN_HOSTS_PATH
            sm.KNOWN_HOSTS_PATH = os.path.join(tmp, "nested", "dir", "known_hosts")
            try:
                client = paramiko.SSHClient()
                SSHManager._prepare_host_key_policy(client)
                client.save_host_keys(sm.KNOWN_HOSTS_PATH)
                self.assertTrue(os.path.isfile(sm.KNOWN_HOSTS_PATH))
            finally:
                sm.KNOWN_HOSTS_PATH = original

    def test_safe_policy_does_not_raise_when_save_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = paramiko.SSHClient()
            SSHManager._prepare_host_key_policy(client)
            policy = sm._SafeAutoAddPolicy()
            # Puntero a una ruta no escribible para simular un fallo al guardar
            client._host_keys_filename = os.path.join(tmp, "no_such_dir", "known_hosts")
            try:
                policy.missing_host_key(client, "example.com", paramiko.RSAKey.generate(1024))
            except Exception as exc:
                self.fail(f"_SafeAutoAddPolicy no debe lanzar excepciones: {exc}")

    def test_handle_terminal_cleans_up_on_disconnect(self):
        sm.active_sessions.clear()
        client = _FakeClient()
        ws = _FakeWS()

        async def run():
            await SSHManager.handle_terminal(ws, "sess-disconnect", client)
            return client.closed, ("sess-disconnect" in sm.active_sessions)

        closed, still_registered = asyncio.run(run())
        self.assertTrue(closed, "El cliente SSH debe cerrarse al desconectar el WebSocket")
        self.assertFalse(still_registered, "La sesión debe quitarse de active_sessions")

    def test_close_session_unknown_is_noop(self):
        sm.active_sessions.clear()
        SSHManager.close_session("no-existe")  # No debe lanzar

    def test_close_session_closes_client(self):
        sm.active_sessions.clear()
        client = _FakeClient()
        sm.active_sessions["sess-manual"] = {"client": client, "channel": client.channel}
        SSHManager.close_session("sess-manual")
        self.assertTrue(client.closed)
        self.assertNotIn("sess-manual", sm.active_sessions)

    def test_handle_ws_accepts_and_cleans_up(self):
        from database import engine, SessionLocal
        import models.models as m

        sm.active_sessions.clear()
        m.Base.metadata.create_all(bind=engine)

        user_id = "u1"
        cred_id = "c1"
        sess_id = "sess-handle-ws"

        db = SessionLocal()
        db.add(m.User(id=user_id, email="u@test.com", password_hash="h", role=m.UserRole.ADMIN))
        db.add(m.Credential(
            id=cred_id, host="10.0.0.1", username="root",
            password_encrypted="enc", created_by=user_id,
        ))
        db.add(m.SSHSession(id=sess_id, user_id=user_id, credential_id=cred_id, is_active=True))
        db.commit()
        db.close()

        client = _FakeClient()

        async def fake_connect(cred):
            return client, None

        original = sm.SSHManager.connect
        sm.SSHManager.connect = staticmethod(fake_connect)
        ws = _FakeWSAccept()
        try:
            asyncio.run(sm.SSHManager.handle_ws(ws, sess_id))
        finally:
            sm.SSHManager.connect = original

        self.assertTrue(ws.accepted, "El WebSocket debe aceptarse antes de enviar datos")
        self.assertTrue(client.closed)
        joined = "\n".join(ws.sent)
        self.assertIn("Conectando a root@10.0.0.1", joined)
        self.assertIn("Conectado exitosamente", joined)

        db = SessionLocal()
        try:
            row = db.query(m.SSHSession).filter(m.SSHSession.id == sess_id).first()
            self.assertFalse(row.is_active)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
