from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

from database import SessionLocal
from models.models import SystemSetting

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
POLL_TIMEOUT = 25
LEASE_SECONDS = 40


def get_setting(key: str) -> str | None:
    db = SessionLocal()
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        return row.value if row else None
    finally:
        db.close()


def set_setting(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def get_bot_token() -> str | None:
    return get_setting("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")


def get_chat_id() -> str | None:
    return get_setting("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")


def _api(method: str, payload: dict, timeout: int = 30) -> dict:
    token = get_bot_token()
    if not token:
        raise RuntimeError("Token de bot de Telegram no configurado")
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def send_message(text: str, chat_id: str | None = None) -> bool:
    try:
        cid = chat_id or get_chat_id()
        if not cid:
            return False
        result = _api("sendMessage", {"chat_id": cid, "text": text, "parse_mode": "HTML"})
        return bool(result.get("ok"))
    except Exception as exc:
        logger.warning("No se pudo enviar mensaje de Telegram: %s", exc)
        return False


def notify_login(email: str, ip: str | None) -> None:
    try:
        send_message(
            "🔐 <b>Inicio de sesión</b>\n"
            f"👤 {email}\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"🌐 IP: {ip or 'desconocida'}"
        )
    except Exception as exc:
        logger.warning("Error notificando inicio de sesión: %s", exc)


def _acquire_lease() -> bool:
    """Elegir un único worker para el polling (multi-worker seguro)."""
    db = SessionLocal()
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == "telegram_poll_lease").first()
        now = time.time()
        if row and row.value:
            try:
                if float(row.value) > now:
                    return False
            except ValueError:
                pass
        if row:
            row.value = str(now + LEASE_SECONDS)
        else:
            db.add(SystemSetting(key="telegram_poll_lease", value=str(now + LEASE_SECONDS)))
        db.commit()
        return True
    except Exception as exc:
        logger.warning("Error adquiriendo lease de polling: %s", exc)
        return False
    finally:
        db.close()


def _handle_start(chat: dict) -> None:
    cid = str(chat.get("id") or "")
    if not cid:
        return
    set_setting("telegram_chat_id", cid)
    first = chat.get("first_name") or ""
    send_message(
        "👋 ¡Hola" + (f" {first}" if first else "") + "!\n\n"
        "Tu chat quedó vinculado al Gestor de Contraseñas.\n"
        "Aquí recibirás los avisos de sesión y los códigos de recuperación.",
        cid,
    )


async def _poll_loop() -> None:
    offset = 0
    while True:
        try:
            if not await asyncio.to_thread(_acquire_lease):
                await asyncio.sleep(5)
                continue
            updates = await asyncio.to_thread(
                _api,
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": ["message"],
                },
                POLL_TIMEOUT + 10,
            )
            for upd in updates.get("result", []):
                offset = upd.get("update_id", 0) + 1
                message = upd.get("message", {})
                chat = message.get("chat", {})
                text = (message.get("text") or "").strip()
                if text == "/start":
                    await asyncio.to_thread(_handle_start, chat)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Error en polling de Telegram: %s", exc)
            await asyncio.sleep(10)


_polling_task: asyncio.Task | None = None


def start_polling() -> None:
    """Iniciar el polling del bot en segundo plano (una sola vez por proceso)."""
    global _polling_task
    if not get_bot_token():
        return
    if _polling_task and not _polling_task.done():
        return
    try:
        _polling_task = asyncio.create_task(_poll_loop())
        logger.info("🚀 Polling de Telegram iniciado")
    except RuntimeError as exc:
        _polling_task = None
        logger.warning("No se pudo iniciar el polling de Telegram: %s", exc)
