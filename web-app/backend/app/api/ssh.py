from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
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
    """WebSocket para terminal SSH interactivo"""
    await websocket.accept()
    
    # Obtener sesión de la base de datos
    db = next(get_db())
    ssh_session = db.query(SSHSession).filter(SSHSession.id == session_id).first()
    
    if not ssh_session or not ssh_session.is_active:
        await websocket.send_text("\r\n❌ Error: Sesión no válida o expirada\r\n")
        await websocket.close(code=1008, reason="Sesión no válida")
        return
    
    # Obtener credencial
    credential = db.query(Credential).filter(Credential.id == ssh_session.credential_id).first()
    
    if not credential:
        await websocket.send_text("\r\n❌ Error: Credencial no encontrada\r\n")
        await websocket.close(code=1008, reason="Credencial no encontrada")
        return
    
    try:
        # Enviar mensaje de conexión
        await websocket.send_text(f"\r\n🔄 Conectando a {credential.username}@{credential.host}:{credential.port or 22}...\r\n")
        
        # Conectar SSH
        client, error = await SSHManager.connect(credential)
        
        if error:
            # Enviar error al cliente
            await websocket.send_text(f"\r\n{error}\r\n")
            await websocket.send_text("\r\n💡 Sugerencias:\r\n")
            await websocket.send_text("   • Verifica que el usuario y contraseña sean correctos\r\n")
            await websocket.send_text("   • Asegúrate de que el servidor SSH esté accesible\r\n")
            await websocket.send_text("   • Verifica el puerto (por defecto: 22)\r\n")
            await websocket.close(code=1011, reason=error)
            
            # Marcar sesión como terminada
            ssh_session.is_active = False
            ssh_session.ended_at = datetime.utcnow()
            db.commit()
            db.close()
            return
        
        # Conexión exitosa
        await websocket.send_text(f"\r\n✅ Conectado exitosamente a {credential.host}\r\n")
        await websocket.send_text("━" * 60 + "\r\n\r\n")
        
        # Manejar terminal
        await SSHManager.handle_terminal(websocket, session_id, client)
        
    except WebSocketDisconnect:
        print(f"WebSocket desconectado para sesión {session_id}")
    except Exception as e:
        error_msg = f"❌ Error inesperado: {str(e)}"
        print(error_msg)
        try:
            await websocket.send_text(f"\r\n{error_msg}\r\n")
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
    finally:
        # Marcar sesión como terminada
        ssh_session.is_active = False
        ssh_session.ended_at = datetime.utcnow()
        db.commit()
        db.close()

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
