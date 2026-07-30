from datetime import timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from models.models import User, Organization, UserRole
from core.security import verify_password, get_password_hash, create_access_token, validate_password_requirements
from config import get_settings

settings = get_settings()


def register_user(db: Session, user_data) -> User:
    is_valid, message = validate_password_requirements(user_data.password)
    if not is_valid:
        raise ValueError(message)

    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise ValueError("El correo ya está registrado")

    org_id = user_data.organization_id
    if not org_id:
        org = Organization(name=f"Organización de {user_data.full_name or user_data.email}")
        db.add(org)
        db.flush()
        org_id = org.id

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        organization_id=org_id,
    )

    users_in_org = db.query(User).filter(User.organization_id == org_id).count()
    if users_in_org == 0:
        user.role = UserRole.ADMIN

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(user: User, password: str) -> Tuple[bool, Optional[str]]:
    if not user or not verify_password(password, user.password_hash):
        return False, "Credenciales incorrectas"

    if not user.is_active:
        return False, "Usuario inactivo"

    return True, None


def create_user_token(user: User) -> str:
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    return create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "org_id": user.organization_id,
        },
        expires_delta=access_token_expires,
    )
