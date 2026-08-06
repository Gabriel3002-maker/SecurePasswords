from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi import Header
from sqlalchemy.orm import Session
from database import get_db
from models.models import User, UserRole
from schemas.schemas import UserCreate, UserLogin, Token, UserResponse, ChangePasswordRequest
from services.auth_service import register_user, authenticate_user, create_user_token
from config import get_settings
from api.deps import get_current_user, get_current_admin
from core.security import get_password_hash, verify_password, validate_password_requirements
from core.rate_limit import RateLimiter
import secrets
import math
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_LOGIN_ATTEMPTS = 5
MAX_IP_ATTEMPTS = 20
LOGIN_LOCKOUT_MINUTES = 15

email_limiter = RateLimiter("login:email", MAX_LOGIN_ATTEMPTS, LOGIN_LOCKOUT_MINUTES * 60)
ip_limiter = RateLimiter("login:ip", MAX_IP_ATTEMPTS, LOGIN_LOCKOUT_MINUTES * 60)


def _raise_rate_limited(remaining_seconds: int) -> None:
    minutos = max(1, math.ceil(remaining_seconds / 60))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiados intentos. Intenta de nuevo en {minutos} minutos.",
    )


def _check_rate_limit(email: str, ip: str) -> None:
    remaining = email_limiter.remaining_lockout(email)
    if remaining:
        logger.warning("Rate limit excedido para %s", email)
        _raise_rate_limited(remaining)
    remaining = ip_limiter.remaining_lockout(ip)
    if remaining:
        logger.warning("Rate limit excedido para IP %s", ip)
        _raise_rate_limited(remaining)

def _set_auth_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=settings.cookie_secure,
    )

def _set_csrf_cookie(response: Response) -> str:
    token = secrets.token_hex(32)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=True,
        max_age=3600,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return token

@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Registrar nuevo usuario (solo admin, siempre como usuario normal de su organización)"""
    user_data.organization_id = current_admin.organization_id
    user_data.role = UserRole.USER
    try:
        return register_user(db, user_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc

@router.post("/login", response_model=Token)
def login(response: Response, request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Iniciar sesión"""
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(credentials.email, ip)

    user = db.query(User).filter(User.email == credentials.email).first()
    is_valid, error = authenticate_user(user, credentials.password)
    email_limiter.record(credentials.email, is_valid)
    ip_limiter.record(ip, is_valid)

    if not is_valid:
        if error == "Usuario inactivo":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_user_token(user)
    _set_auth_cookie(response, access_token)
    csrf = _set_csrf_cookie(response)

    from core import telegram as telegram_service
    try:
        telegram_service.notify_login(credentials.email, request.client.host if request.client else None)
    except Exception:
        pass

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "csrf_token": csrf,
    }

@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambiar contraseña maestra (login)"""
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    valid, msg = validate_password_requirements(data.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Contraseña actualizada exitosamente"}

@router.post("/logout")
def logout(response: Response):
    """Cerrar sesión"""
    response.delete_cookie("access_token")
    return {"message": "Sesión cerrada exitosamente"}
