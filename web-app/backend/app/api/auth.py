from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi import Header
from sqlalchemy.orm import Session
from database import get_db
from models.models import User
from schemas.schemas import UserCreate, UserLogin, Token, UserResponse, ChangePasswordRequest
from services.auth_service import register_user, authenticate_user, create_user_token
from config import get_settings
from api.deps import get_current_user
from core.security import get_password_hash, verify_password, validate_password_requirements
import secrets
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])

_INVALID_ATTEMPTS: dict[str, int] = {}
MAX_LOGIN_ATTEMPTS = 5

def _check_rate_limit(email: str) -> None:
    attempts = _INVALID_ATTEMPTS.get(email, 0)
    if attempts >= MAX_LOGIN_ATTEMPTS:
        logger.warning("Rate limit excedido para %s", email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Intenta de nuevo en 15 minutos."
        )

def _record_attempt(email: str, success: bool) -> None:
    if success:
        _INVALID_ATTEMPTS.pop(email, None)
    else:
        _INVALID_ATTEMPTS[email] = _INVALID_ATTEMPTS.get(email, 0) + 1

def _set_auth_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        expires=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=not settings.debug,
    )

def _set_csrf_cookie(response: Response) -> str:
    token = secrets.token_hex(32)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=True,
        max_age=3600,
        samesite="lax",
        secure=not settings.debug,
    )
    return token

@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Registrar nuevo usuario"""
    try:
        return register_user(db, user_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc

@router.post("/login", response_model=Token)
def login(response: Response, credentials: UserLogin, db: Session = Depends(get_db)):
    """Iniciar sesión"""
    _check_rate_limit(credentials.email)

    user = db.query(User).filter(User.email == credentials.email).first()
    is_valid, error = authenticate_user(user, credentials.password)
    _record_attempt(credentials.email, is_valid)

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
