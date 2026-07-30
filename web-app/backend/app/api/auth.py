from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from database import get_db
from models.models import User
from schemas.schemas import UserCreate, UserLogin, Token, UserResponse
from services.auth_service import register_user, authenticate_user, create_user_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

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
    user = db.query(User).filter(User.email == credentials.email).first()
    is_valid, error = authenticate_user(user, credentials.password)

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

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=60 * 60,
        expires=60 * 60,
        samesite="lax",
        secure=False,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }

@router.post("/logout")
def logout(response: Response):
    """Cerrar sesión"""
    response.delete_cookie("access_token")
    return {"message": "Sesión cerrada exitosamente"}
