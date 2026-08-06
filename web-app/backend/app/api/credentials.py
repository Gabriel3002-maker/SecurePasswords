from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import datetime
import json
from database import get_db
from models.models import User, Credential, CredentialPermission, UserRole, Tag, AuditLog, credential_tags
from schemas.schemas import (
    CredentialCreate, CredentialUpdate, CredentialResponse, 
    CredentialWithPassword, PermissionCreate, PermissionResponse,
    TagCreate, TagResponse, AuditLogResponse, GeneratePasswordRequest, GeneratePasswordResponse
)
from api.deps import get_current_user, get_current_admin
from core.encryption import encrypt_password, decrypt_password
from core.security import get_duplicate_hash

def _log_audit(db: Session, user_id: str, action: str, resource_type: str, resource_id: str, details: dict = None, ip: str = ""):
    log = AuditLog(
        user_id=user_id, action=action, resource_type=resource_type,
        resource_id=resource_id, details=json.dumps(details) if details else None,
        ip_address=ip
    )
    db.add(log)

router = APIRouter(prefix="/credentials", tags=["Credentials"])


def _has_permission(user: User, credential: Credential, db: Session, permission_type: str) -> bool:
    if user.role == UserRole.ADMIN and user.organization_id == credential.organization_id:
        return True
    if credential.created_by == user.id:
        return True
    permission = db.query(CredentialPermission).filter(and_(
        CredentialPermission.credential_id == credential.id,
        CredentialPermission.user_id == user.id,
        getattr(CredentialPermission, permission_type) == True
    )).first()
    return permission is not None


def user_can_view_credential(user: User, credential: Credential, db: Session) -> bool:
    return _has_permission(user, credential, db, "can_view")


def _get_user_permissions(user: User, credential: Credential, db: Session) -> dict:
    # Admins y dueños de la credencial siempre tienen acceso completo
    if user.role == UserRole.ADMIN and user.organization_id == credential.organization_id:
        return {"can_view": True, "can_edit": True, "can_delete": True, "can_connect_ssh": True}
    if credential.created_by == user.id:
        return {"can_view": True, "can_edit": True, "can_delete": True, "can_connect_ssh": True}
    permission = db.query(CredentialPermission).filter(and_(
        CredentialPermission.credential_id == credential.id,
        CredentialPermission.user_id == user.id
    )).first()
    if permission:
        return {
            "can_view": permission.can_view,
            "can_edit": permission.can_edit,
            "can_delete": permission.can_delete,
            "can_connect_ssh": permission.can_connect_ssh,
        }
    return {"can_view": False, "can_edit": False, "can_delete": False, "can_connect_ssh": False}

# ─── Static Routes (must come before /{credential_id}) ─────────

@router.get("/", response_model=List[CredentialResponse])
def list_credentials(
    request: Request,
    folder: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar credenciales activas según permisos del usuario"""
    if current_user.role == UserRole.ADMIN:
        q = db.query(Credential).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == False
        )
        if folder is not None and folder != "Favoritos":
            q = q.filter(Credential.folder == folder)
        if search:
            q = q.filter(
                Credential.host.ilike(f"%{search}%") |
                Credential.username.ilike(f"%{search}%") |
                Credential.comment.ilike(f"%{search}%")
            )
        if tag:
            q = q.join(credential_tags).join(Tag).filter(Tag.name == tag)
        if is_favorite is not None:
            q = q.filter(Credential.is_favorite == is_favorite)
        if folder == "Favoritos":
            q = q.filter(Credential.is_favorite == True)
        results = q.order_by(Credential.updated_at.desc()).all()
    else:
        # Usuarios normales: sus propias credenciales + las compartidas con ellos
        owned = db.query(Credential.id).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == False
        )
        shared = db.query(Credential.id).join(
            CredentialPermission,
            CredentialPermission.credential_id == Credential.id
        ).filter(
            CredentialPermission.user_id == current_user.id,
            CredentialPermission.can_view == True,
            Credential.is_deleted == False
        )
        q = db.query(Credential).filter(Credential.id.in_(owned.union(shared)))
        if folder is not None and folder != "Favoritos":
            q = q.filter(Credential.folder == folder)
        if search:
            q = q.filter(
                Credential.host.ilike(f"%{search}%") |
                Credential.username.ilike(f"%{search}%") |
                Credential.comment.ilike(f"%{search}%")
            )
        if tag:
            q = q.join(credential_tags).join(Tag).filter(Tag.name == tag)
        if is_favorite is not None:
            q = q.filter(Credential.is_favorite == is_favorite)
        if folder == "Favoritos":
            q = q.filter(Credential.is_favorite == True)
        results = q.order_by(Credential.updated_at.desc()).all()
    
    # Agregar nombres de etiquetas y permisos del usuario actual
    for c in results:
        c.tags = [t.name for t in c.tags_rel]
        c.user_permissions = _get_user_permissions(current_user, c, db)
    return results


@router.get("/trash", response_model=List[CredentialResponse])
def list_trash(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar credenciales en la papelera"""
    if current_user.role == UserRole.ADMIN:
        q = db.query(Credential).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == True
        )
    else:
        q = db.query(Credential).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == True
        )
    results = q.order_by(Credential.deleted_at.desc()).all()
    for c in results:
        c.tags = [t.name for t in c.tags_rel]
    return results


@router.delete("/trash/empty", status_code=status.HTTP_204_NO_CONTENT)
def empty_trash(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Vaciar la papelera (eliminar permanentemente todas las credenciales eliminadas)"""
    if current_user.role == UserRole.ADMIN:
        q = db.query(Credential).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == True
        )
    else:
        q = db.query(Credential).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == True
        )
    trash = q.all()
    for c in trash:
        db.query(CredentialPermission).filter(CredentialPermission.credential_id == c.id).delete()
        db.delete(c)
    db.commit()


@router.get("/folders/count")
def count_by_folder(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Contar credenciales activas por carpeta"""
    if current_user.role == UserRole.ADMIN:
        q = db.query(Credential.folder, func.count(Credential.id)).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == False
        )
    else:
        q = db.query(Credential.folder, func.count(Credential.id)).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == False
        )
    counts = q.group_by(Credential.folder).all()
    total = sum(c[1] for c in counts)
    if current_user.role == UserRole.ADMIN:
        fav_q = db.query(func.count(Credential.id)).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == False,
            Credential.is_favorite == True
        )
    else:
        fav_q = db.query(func.count(Credential.id)).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == False,
            Credential.is_favorite == True
        )
    favorites = fav_q.scalar() or 0
    return {
        "total": total,
        "folders": {f or "General": c for f, c in counts},
        "favorites": favorites,
    }


@router.post("/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(
    request: Request,
    credential_data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear nueva credencial"""
    password_encrypted = encrypt_password(credential_data.password)
    token_encrypted = encrypt_password(credential_data.token) if credential_data.token else None
    password_hash = get_duplicate_hash(credential_data.password)
    
    credential = Credential(
        host=credential_data.host,
        username=credential_data.username,
        password_encrypted=password_encrypted,
        token_encrypted=token_encrypted,
        password_hash=password_hash,
        port=credential_data.port,
        comment=credential_data.comment,
        folder=credential_data.folder or "",
        created_by=current_user.id,
        organization_id=current_user.organization_id
    )
    
    db.add(credential)
    db.flush()
    
    # Asignar etiquetas si se proporcionaron
    if credential_data.tags:
        for name in credential_data.tags:
            tag = db.query(Tag).filter(
                Tag.name == name, Tag.organization_id == current_user.organization_id
            ).first()
            if not tag:
                tag = Tag(name=name, organization_id=current_user.organization_id)
                db.add(tag)
                db.flush()
            credential.tags_rel.append(tag)
    
    db.commit()
    db.refresh(credential)
    
    ip = request.client.host if request.client else ""
    _log_audit(db, current_user.id, "created", "credential", credential.id, {"host": credential.host, "username": credential.username}, ip)
    db.commit()
    
    return credential


# ─── Tags ───────────────────────────────────────────────────────

@router.get("/tags", response_model=List[TagResponse])
def list_tags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Tag).filter(Tag.organization_id == current_user.organization_id).all()


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(Tag).filter(Tag.name == tag_data.name, Tag.organization_id == current_user.organization_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="La etiqueta ya existe")
    tag = Tag(name=tag_data.name, color=tag_data.color, organization_id=current_user.organization_id)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(
    tag_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.organization_id == current_user.organization_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    db.delete(tag)
    db.commit()


# ─── Audit Log ──────────────────────────────────────────────────

@router.get("/audit", response_model=List[AuditLogResponse])
def global_audit(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return (
        db.query(AuditLog)
        .join(User, AuditLog.user_id == User.id)
        .filter(User.organization_id == current_user.organization_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(100)
        .all()
    )


# ─── Duplicate & Weak Password Detection ────────────────────────

@router.get("/duplicates")
def find_duplicates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.ADMIN:
        q = db.query(Credential).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == False,
            Credential.password_hash.isnot(None)
        )
    else:
        q = db.query(Credential).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == False,
            Credential.password_hash.isnot(None)
        )
    creds = q.all()
    from collections import Counter
    groups = Counter(c.password_hash for c in creds if c.password_hash)
    duplicates = {h: [] for h, count in groups.items() if count > 1}
    for c in creds:
        if c.password_hash in duplicates:
            duplicates[c.password_hash].append({"id": c.id, "host": c.host, "username": c.username, "folder": c.folder})
    return [{"password_hash": h, "count": len(creds), "credentials": creds} for h, creds in duplicates.items()]


@router.get("/weak")
def find_weak(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from core.security import validate_password_requirements
    if current_user.role == UserRole.ADMIN:
        q = db.query(Credential).filter(
            Credential.organization_id == current_user.organization_id,
            Credential.is_deleted == False
        )
    else:
        q = db.query(Credential).filter(
            Credential.created_by == current_user.id,
            Credential.is_deleted == False
        )
    weak = []
    for cred in q.all():
        try:
            pw = decrypt_password(cred.password_encrypted)
            valid, msg = validate_password_requirements(pw)
            if not valid:
                weak.append({"id": cred.id, "host": cred.host, "username": cred.username, "folder": cred.folder, "issues": [msg]})
        except Exception:
            pass
    return weak


# ─── Password Generator ─────────────────────────────────────────

@router.post("/generate-password", response_model=GeneratePasswordResponse)
def generate_password(
    data: GeneratePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    import secrets, string

    grupos = []
    if data.uppercase: grupos.append(string.ascii_uppercase)
    if data.lowercase: grupos.append(string.ascii_lowercase)
    if data.numbers:   grupos.append(string.digits)
    if data.symbols:   grupos.append("!@#$%^&*()_+-=[]{}|;:,.<>?")
    if not grupos:     grupos = [string.ascii_letters, string.digits]

    alfabeto = "".join(grupos)
    if data.length < len(grupos):
        raise HTTPException(
            status_code=400,
            detail=f"La longitud mínima para los tipos elegidos es {len(grupos)}.",
        )

    # Un carácter de cada clase pedida + el resto del alfabeto completo.
    chars = [secrets.choice(g) for g in grupos]
    chars += [secrets.choice(alfabeto) for _ in range(data.length - len(grupos))]

    # Barajado criptográficamente seguro (random.shuffle reintroduciría la debilidad).
    secrets.SystemRandom().shuffle(chars)
    return {"password": "".join(chars)}


# ─── Credential-by-ID Routes (must come after static routes) ───

@router.get("/{credential_id}", response_model=CredentialWithPassword)
def get_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener credencial con contraseña desencriptada"""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    
    if not credential or credential.is_deleted:
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
    request: Request,
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
    
    if not _has_permission(current_user, credential, db, "can_edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para editar esta credencial"
        )
    
    update_data = credential_data.model_dump(exclude_unset=True)
    changes = {}

    if "password" in update_data and update_data["password"]:
        pwd = update_data.pop("password")
        update_data["password_encrypted"] = encrypt_password(pwd)
        update_data["password_hash"] = get_duplicate_hash(pwd)
        changes["password"] = "actualizada"

    if "token" in update_data and update_data["token"]:
        update_data["token_encrypted"] = encrypt_password(update_data.pop("token"))
        changes["token"] = "actualizado"

    if "folder" in update_data and update_data["folder"] is None:
        update_data["folder"] = ""
    
    if "tags" in update_data:
        update_data.pop("tags")
        changes["tags"] = "actualizadas"
    
    for key, value in update_data.items():
        if key != "tags" and key != "password" and key != "token":
            old = getattr(credential, key, None)
            if old != value:
                changes[key] = f"{old} → {value}" if old else str(value)
        setattr(credential, key, value)
    
    db.commit()
    db.refresh(credential)
    
    ip = request.client.host if request.client else ""
    _log_audit(db, current_user.id, "updated", "credential", credential.id, changes, ip)
    db.commit()
    
    return credential


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    request: Request,
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mover a la papelera (soft delete)"""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada"
        )
    
    if not _has_permission(current_user, credential, db, "can_delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar esta credencial"
        )
    
    credential.is_deleted = True
    credential.deleted_at = datetime.utcnow()
    ip = request.client.host if request.client else ""
    _log_audit(db, current_user.id, "deleted", "credential", credential.id, {"host": credential.host}, ip)
    db.commit()


@router.delete("/{credential_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar permanentemente (solo desde la papelera)"""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.is_deleted == True
    ).first()
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada en la papelera")
    if not _has_permission(current_user, credential, db, "can_delete"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso")
    db.query(CredentialPermission).filter(CredentialPermission.credential_id == credential.id).delete()
    db.delete(credential)
    db.commit()


@router.post("/{credential_id}/restore", response_model=CredentialResponse)
def restore_credential(
    request: Request,
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restaurar credencial de la papelera"""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.is_deleted == True
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada en la papelera"
        )
    
    if not _has_permission(current_user, credential, db, "can_delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para restaurar esta credencial"
        )
    
    credential.is_deleted = False
    credential.deleted_at = None
    ip = request.client.host if request.client else ""
    _log_audit(db, current_user.id, "restored", "credential", credential.id, {"host": credential.host}, ip)
    db.commit()
    db.refresh(credential)
    return credential


# ─── Permissions (admin only) ───────────────────────────────────

@router.post("/{credential_id}/permissions", response_model=PermissionResponse)
def grant_permission(
    credential_id: str,
    permission_data: PermissionCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Asignar permiso a un usuario (solo admin)"""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.organization_id,
    ).first()
    
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
    credential.is_shared = True
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
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.organization_id,
    ).first()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada",
        )

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
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.organization_id,
    ).first()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada",
        )

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


# ─── Tag Assignment & History (per-credential) ──────────────────

@router.post("/{credential_id}/tags", response_model=CredentialResponse)
def assign_tags(
    request: Request,
    credential_id: str,
    tag_names: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    if not _has_permission(current_user, credential, db, "can_edit"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    credential.tags_rel = []
    for name in tag_names:
        tag = db.query(Tag).filter(Tag.name == name, Tag.organization_id == current_user.organization_id).first()
        if not tag:
            tag = Tag(name=name, organization_id=current_user.organization_id)
            db.add(tag)
            db.flush()
        credential.tags_rel.append(tag)
    db.commit()
    db.refresh(credential)
    return credential


@router.get("/{credential_id}/history", response_model=List[AuditLogResponse])
def credential_history(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    if not user_can_view_credential(current_user, credential, db):
        raise HTTPException(status_code=403, detail="Sin permiso")
    logs = db.query(AuditLog).filter(
        AuditLog.resource_type == "credential",
        AuditLog.resource_id == credential_id
    ).order_by(AuditLog.timestamp.desc()).limit(50).all()
    return logs
