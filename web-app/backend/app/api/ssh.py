from fastapi import APIRouter, Depends, HTTPException, status, WebSocket
from sqlalchemy.orm import Session
from database import get_db
from models.models import User, Credential, SSHSession, CredentialPermission
from schemas.schemas import SSHConnectionRequest, SSHConnectionResponse
from api.deps import get_current_user
from core.ssh_manager import SSHManager
from datetime import datetime
import uuid

router = APIRouter(prefix="/ssh", tags=["SSH"])

@router.post("/connect", response_model=SSHConnectionResponse)
async def connect_ssh(
    request: SSHConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Iniciar conexión SSH"""
    # Verificar que la credencial existe
    credential = db.query(Credential).filter(Credential.id == request.credential_id).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credencial no encontrada"
        )
    
    # Verificar permisos SSH
    has_permission = False
    if credential.created_by == current_user.id:
        has_permission = True
    else:
        permission = db.query(CredentialPermission).filter(
            CredentialPermission.credential_id == request.credential_id,
            CredentialPermission.user_id == current_user.id,
            CredentialPermission.can_connect_ssh == True
        ).first()
        has_permission = permission is not None
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para conectar SSH con esta credencial"
        )
    
    # Crear sesión SSH en la base de datos
    session_id = str(uuid.uuid4())
    ssh_session = SSHSession(
        id=session_id,
        user_id=current_user.id,
        credential_id=request.credential_id,
        is_active=True
    )
    
    db.add(ssh_session)
    db.commit()
    
    return {
        "session_id": session_id,
        "websocket_url": f"/api/ssh/terminal/{session_id}"
    }

@router.websocket("/terminal/{session_id}")
async def ssh_terminal(websocket: WebSocket, session_id: str):
    """WebSocket para terminal SSH interactivo (multi-sesión)."""
    await SSHManager.handle_ws(websocket, session_id)

@router.post("/disconnect/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_ssh(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cerrar sesión SSH"""
    ssh_session = db.query(SSHSession).filter(
        SSHSession.id == session_id,
        SSHSession.user_id == current_user.id
    ).first()
    
    if not ssh_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada"
        )
    
    # Cerrar conexión SSH
    SSHManager.close_session(session_id)
    
    # Actualizar base de datos
    ssh_session.is_active = False
    ssh_session.ended_at = datetime.utcnow()
    db.commit()
