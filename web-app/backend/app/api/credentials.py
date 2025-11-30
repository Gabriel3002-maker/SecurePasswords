from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.models import User, Credential, CredentialPermission, UserRole
from schemas.schemas import (
    CredentialCreate, CredentialUpdate, CredentialResponse, 
    CredentialWithPassword, PermissionCreate, PermissionResponse
)
from api.deps import get_current_user, get_current_admin
from core.encryption import encrypt_password, decrypt_password

router = APIRouter(prefix="/credentials", tags=["Credentials"])

def user_can_view_credential(user: User, credential: Credential, db: Session) -> bool:
    """Verificar si el usuario puede ver una credencial"""
    # Admin puede ver todo
    if user.role == UserRole.ADMIN and user.organization_id == credential.organization_id:
        return True
    
    # Creador puede ver sus propias credenciales
    if credential.created_by == user.id:
        return True
    
    # Verificar permisos explícitos
    permission = db.query(CredentialPermission).filter(
        CredentialPermission.credential_id == credential.id,
        CredentialPermission.user_id == user.id,
        CredentialPermission.can_view == True
    ).first()
    
    return permission is not None

@router.get("/", response_model=List[CredentialResponse])
def list_credentials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar credenciales según permisos del usuario"""
    if current_user.role == UserRole.ADMIN:
        # Admin ve todas las credenciales de su organización
        credentials = db.query(Credential).filter(
            Credential.organization_id == current_user.organization_id
        ).all()
    else:
        # Usuario normal ve solo sus credenciales y las compartidas con él
        own_credentials = db.query(Credential).filter(
            Credential.created_by == current_user.id
        ).all()
        
        # Credenciales compartidas
        shared_permissions = db.query(CredentialPermission).filter(
            CredentialPermission.user_id == current_user.id,
            CredentialPermission.can_view == True
        ).all()
        
        shared_credential_ids = [p.credential_id for p in shared_permissions]
        shared_credentials = db.query(Credential).filter(
            Credential.id.in_(shared_credential_ids)
        ).all() if shared_credential_ids else []
        
        credentials = own_credentials + shared_credentials
    
    # Agregar permisos del usuario a cada credencial
    result = []
    for cred in credentials:
        cred_dict = {
            "id": cred.id,
            "host": cred.host,
            "username": cred.username,
            "port": cred.port,
            "comment": cred.comment,
            "is_shared": cred.is_shared,
            "created_by": cred.created_by,
            "organization_id": cred.organization_id,
            "created_at": cred.created_at,
            "updated_at": cred.updated_at,
        }
        
        # Determinar permisos del usuario
        if current_user.role == UserRole.ADMIN or cred.created_by == current_user.id:
            # Admin o creador tiene todos los permisos
            cred_dict["user_permissions"] = {
                "can_view": True,
                "can_edit": True,
                "can_delete": True,
                "can_connect_ssh": True
            }
        else:
            # Buscar permisos explícitos
            permission = db.query(CredentialPermission).filter(
                CredentialPermission.credential_id == cred.id,
                CredentialPermission.user_id == current_user.id
            ).first()
            
            if permission:
                cred_dict["user_permissions"] = {
                    "can_view": permission.can_view,
                    "can_edit": permission.can_edit,
                    "can_delete": permission.can_delete,
                    "can_connect_ssh": permission.can_connect_ssh
                }
            else:
                cred_dict["user_permissions"] = {
                    "can_view": False,
                    "can_edit": False,
                    "can_delete": False,
                    "can_connect_ssh": False
                }
        
        result.append(cred_dict)
    
    return result

@router.post("/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(
    credential_data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear nueva credencial"""
    # Encriptar contraseña y token
    encrypted_password = encrypt_password(credential_data.password)
    encrypted_token = encrypt_password(credential_data.token) if credential_data.token else None
    
    credential = Credential(
        host=credential_data.host,
        username=credential_data.username,
        password_encrypted=encrypted_password,
        token_encrypted=encrypted_token,
        port=credential_data.port,
        comment=credential_data.comment,
        is_shared=credential_data.is_shared,
        created_by=current_user.id,
        organization_id=current_user.organization_id
    )
    
    db.add(credential)
    db.commit()
    db.refresh(credential)
    
    return credential

@router.get("/{credential_id}", response_model=CredentialWithPassword)
def get_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener credencial con contraseña desencriptada"""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada"
        )
    
    # Verificar permisos
    if not user_can_view_credential(current_user, credential, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta credencial"
        )
    
    # Desencriptar contraseña
    decrypted_password = decrypt_password(credential.password_encrypted)
    decrypted_token = decrypt_password(credential.token_encrypted) if credential.token_encrypted else None
    
    return {
        **credential.__dict__,
        "password": decrypted_password,
        "token": decrypted_token
    }

@router.put("/{credential_id}", response_model=CredentialResponse)
def update_credential(
    credential_id: str,
    credential_data: CredentialUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar credencial"""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada"
        )
    
    # Verificar permisos de edición
    can_edit = False
    if current_user.role == UserRole.ADMIN and current_user.organization_id == credential.organization_id:
        can_edit = True
    elif credential.created_by == current_user.id:
        can_edit = True
    else:
        permission = db.query(CredentialPermission).filter(
            CredentialPermission.credential_id == credential_id,
            CredentialPermission.user_id == current_user.id,
            CredentialPermission.can_edit == True
        ).first()
        can_edit = permission is not None
    
    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para editar esta credencial"
        )
    
    # Actualizar campos
    update_data = credential_data.dict(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        update_data["password_encrypted"] = encrypt_password(update_data.pop("password"))
    
    if "token" in update_data and update_data["token"]:
        update_data["token_encrypted"] = encrypt_password(update_data.pop("token"))
    
    for key, value in update_data.items():
        setattr(credential, key, value)
    
    db.commit()
    db.refresh(credential)
    
    return credential

@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar credencial"""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada"
        )
    
    # Verificar permisos de eliminación
    can_delete = False
    if current_user.role == UserRole.ADMIN and current_user.organization_id == credential.organization_id:
        can_delete = True
    elif credential.created_by == current_user.id:
        can_delete = True
    else:
        permission = db.query(CredentialPermission).filter(
            CredentialPermission.credential_id == credential_id,
            CredentialPermission.user_id == current_user.id,
            CredentialPermission.can_delete == True
        ).first()
        can_delete = permission is not None
    
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar esta credencial"
        )
    
    db.delete(credential)
    db.commit()

# Endpoints de permisos (solo admin)
@router.post("/{credential_id}/permissions", response_model=PermissionResponse)
def grant_permission(
    credential_id: str,
    permission_data: PermissionCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Asignar permiso a un usuario (solo admin)"""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada"
        )
    
    # Verificar que el usuario existe y está en la misma organización
    target_user = db.query(User).filter(User.id == permission_data.user_id).first()
    if not target_user or target_user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en tu organización"
        )
    
    # Verificar si ya existe el permiso
    existing = db.query(CredentialPermission).filter(
        CredentialPermission.credential_id == credential_id,
        CredentialPermission.user_id == permission_data.user_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya tiene permisos sobre esta credencial"
        )
    
    permission = CredentialPermission(
        credential_id=credential_id,
        user_id=permission_data.user_id,
        can_view=permission_data.can_view,
        can_edit=permission_data.can_edit,
        can_delete=permission_data.can_delete,
        can_connect_ssh=permission_data.can_connect_ssh,
        granted_by=current_user.id
    )
    
    db.add(permission)
    db.commit()
    db.refresh(permission)
    
    return permission

@router.get("/{credential_id}/permissions", response_model=List[PermissionResponse])
def list_permissions(
    credential_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Listar permisos de una credencial (solo admin)"""
    permissions = db.query(CredentialPermission).filter(
        CredentialPermission.credential_id == credential_id
    ).all()
    
    return permissions

@router.delete("/{credential_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_permission(
    credential_id: str,
    user_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Revocar permiso de un usuario (solo admin)"""
    permission = db.query(CredentialPermission).filter(
        CredentialPermission.credential_id == credential_id,
        CredentialPermission.user_id == user_id
    ).first()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permiso no encontrado"
        )
    
    db.delete(permission)
    db.commit()
