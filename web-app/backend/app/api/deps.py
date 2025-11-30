from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
from models.models import User, UserRole
from core.security import decode_token



def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Obtener usuario actual desde el token JWT (Header o Cookie)"""
    token = None
    
    # 1. Intentar obtener del header Authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    # 2. Intentar obtener de la cookie
    if not token:
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verificar que el usuario actual sea admin"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user
