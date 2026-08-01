from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from database import SessionLocal
from models.models import RecoveryCode, SystemSetting
from core.security import get_password_hash, verify_password, validate_password_requirements
from core import telegram

router = APIRouter(prefix="/recovery", tags=["Recovery"])

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_TTL_MINUTES = 10


class RecoveryRequest(BaseModel):
    pass


class RecoveryConfirm(BaseModel):
    code: str
    new_master_password: str


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


@router.post("/request")
def request_recovery(request: Request):
    """Solicitar código de recuperación de la contraseña maestra (enviado por Telegram)."""
    if not telegram.get_chat_id():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram no está vinculado. Vincula tu chat enviando /start al bot.",
        )

    code = _generate_code()

    db = SessionLocal()
    try:
        code_row = RecoveryCode(
            purpose="master_password",
            code_hash=get_password_hash(code),
            expires_at=datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
        )
        db.add(code_row)
        db.commit()
    finally:
        db.close()

    ok = telegram.send_message(
        "🔑 <b>Código de recuperación</b>\n\n"
        f"Tu código es: <b>{code}</b>\n"
        f"Expira en {CODE_TTL_MINUTES} minutos.\n"
        "Ingrésalo en la página de recuperación para restablecer tu contraseña maestra."
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo enviar el código por Telegram.",
        )

    return {"message": "Código enviado a tu chat de Telegram."}


@router.post("/confirm")
def confirm_recovery(data: RecoveryConfirm):
    """Confirmar código y restablecer la contraseña maestra."""
    code = data.code.strip().upper()
    new_password = data.new_master_password

    valid, msg = validate_password_requirements(new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    now = datetime.utcnow()
    db = SessionLocal()
    try:
        codes = (
            db.query(RecoveryCode)
            .filter(
                RecoveryCode.purpose == "master_password",
                RecoveryCode.used_at.is_(None),
                RecoveryCode.expires_at > now,
            )
            .order_by(RecoveryCode.created_at.desc())
            .all()
        )
        match = next((c for c in codes if verify_password(code, c.code_hash)), None)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código inválido o expirado.",
            )

        match.used_at = now
        master_row = db.query(SystemSetting).filter(SystemSetting.key == "master_password_hash").first()
        if master_row:
            master_row.value = get_password_hash(new_password)
        else:
            db.add(SystemSetting(key="master_password_hash", value=get_password_hash(new_password)))
        db.commit()
    finally:
        db.close()

    telegram.send_message("✅ Tu contraseña maestra fue restablecida correctamente.")
    return {"message": "Contraseña maestra restablecida correctamente."}
