from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db
from models.models import User, Organization, UserRole
from schemas.schemas import UserCreate, UserLogin, Token, UserResponse
from core.security import verify_password, get_password_hash, create_access_token
from config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Registrar nuevo usuario"""
    # Verificar si el email ya existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo ya está registrado"
        )
    
    # Si no hay organización, crear una nueva
    org_id = user_data.organization_id
    if not org_id:
        # Crear organización automáticamente
        org = Organization(name=f"Organización de {user_data.full_name or user_data.email}")
        db.add(org)
        db.flush()
        org_id = org.id
    
    # Crear usuario
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        organization_id=org_id
    )
    
    # Si es el primer usuario de la organización, hacerlo admin
    users_in_org = db.query(User).filter(User.organization_id == org_id).count()
    if users_in_org == 0:
        user.role = UserRole.ADMIN
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

@router.post("/login", response_model=Token)
def login(response: Response, credentials: UserLogin, db: Session = Depends(get_db)):
    """Iniciar sesión"""
    # Buscar usuario
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    # Crear token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "org_id": user.organization_id
        },
        expires_delta=access_token_expires
    )
    
    # Set cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        expires=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=False # Set to True in production with HTTPS
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/logout")
def logout(response: Response):
    """Cerrar sesión"""
    response.delete_cookie("access_token")
    return {"message": "Sesión cerrada exitosamente"}
