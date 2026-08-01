import os
import paramiko
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
from datetime import datetime
from typing import Dict, Optional
from models.models import SSHSession, Credential
from core.encryption import decrypt_password
from database import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cada sesión mantiene su propio cliente SSH y canal para permitir
# múltiples terminales abiertas de forma concurrente (paneles divididos).
active_sessions: Dict[str, dict] = {}


def _get_known_hosts_path() -> str:
    """Ruta del archivo de host keys conocidos.

    Dentro de Docker se guarda en el volumen persistente /app/data para que
    sobreviva reinicios; si no, se usa ~/.ssh.
    """
    configured = os.getenv("SSH_KNOWN_HOSTS_FILE")
    if configured:
        return configured
    if os.path.isdir("/app/data"):
        return "/app/data/ssh_known_hosts"
    return os.path.join(os.path.expanduser("~/.ssh"), "opencode_known_hosts")


KNOWN_HOSTS_PATH = _get_known_hosts_path()


class _SafeAutoAddPolicy(paramiko.AutoAddPolicy):
    """AutoAddPolicy que nunca rompe la conexión si no se puede guardar la host key."""

    def missing_host_key(self, client, hostname, key):
        client._host_keys.add(hostname, key.get_name(), key)
        if client._host_keys_filename is not None:
            try:
                client.save_host_keys(client._host_keys_filename)
            except Exception as e:
                logger.warning("No se pudo guardar la host key de %s: %s", hostname, e)


class SSHManager:

    @staticmethod
    def _prepare_host_key_policy(client: paramiko.SSHClient) -> None:
        # paramiko 3.x falla si intenta leer/releer el archivo y no existe
        # (load_host_keys / save_host_keys), así que creamos dir y archivo.
        os.makedirs(os.path.dirname(KNOWN_HOSTS_PATH), exist_ok=True)
        if not os.path.exists(KNOWN_HOSTS_PATH):
            open(KNOWN_HOSTS_PATH, "a").close()
        try:
            client.load_host_keys(KNOWN_HOSTS_PATH)
        except FileNotFoundError:
            pass
        client.set_missing_host_key_policy(_SafeAutoAddPolicy())
        logger.warning("SSH host keys stored in %s", KNOWN_HOSTS_PATH)

    @staticmethod
    async def connect(credential: Credential) -> tuple[Optional[paramiko.SSHClient], Optional[str]]:
        client = paramiko.SSHClient()
        SSHManager._prepare_host_key_policy(client)
        
        # Desencriptar contraseña
        try:
            password = decrypt_password(credential.password_encrypted)
        except Exception as e:
            error_msg = f"Error al desencriptar contraseña: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
        
        try:
            logger.info(f"Intentando conectar a {credential.host}:{credential.port or 22} como {credential.username}")
            
            client.connect(
                hostname=credential.host,
                port=credential.port or 22,
                username=credential.username,
                password=password,
                timeout=10,
                look_for_keys=False,  # No usar claves SSH del sistema
                allow_agent=False     # No usar SSH agent
            )
            
            logger.info(f"✅ Conexión SSH exitosa a {credential.host}")
            return client, None
            
        except paramiko.AuthenticationException:
            error_msg = f"❌ Autenticación fallida para {credential.username}@{credential.host}. Verifica el usuario y contraseña."
            logger.error(error_msg)
            return None, error_msg
            
        except paramiko.SSHException as e:
            error_msg = f"❌ Error SSH: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
            
        except TimeoutError:
            error_msg = f"❌ Timeout: No se pudo conectar a {credential.host}:{credential.port or 22}. Verifica que el servidor esté accesible."
            logger.error(error_msg)
            return None, error_msg
            
        except Exception as e:
            error_msg = f"❌ Error inesperado al conectar: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    @staticmethod
    async def handle_ws(websocket: WebSocket, session_id: str):
        """Flujo completo de un terminal interactivo vía WebSocket.

        Cada sesión abre su propia conexión SSH y canal, por lo que pueden
        coexistir múltiples terminales a la vez.
        """
        await websocket.accept()
        db = next(get_db())
        session = None
        client = None
        try:
            session = db.query(SSHSession).filter(SSHSession.id == session_id).first()
            if not session or not session.is_active:
                await websocket.send_text("\r\n❌ Error: Sesión no válida o expirada\r\n")
                await websocket.close(code=1008, reason="Sesión no válida")
                return

            credential = db.query(Credential).filter(Credential.id == session.credential_id).first()
            if not credential:
                await websocket.send_text("\r\n❌ Error: Credencial no encontrada\r\n")
                await websocket.close(code=1008, reason="Credencial no encontrada")
                return

            await websocket.send_text(f"\r\n🔄 Conectando a {credential.username}@{credential.host}:{credential.port or 22}...\r\n")

            client, error = await SSHManager.connect(credential)

            if error:
                await websocket.send_text(f"\r\n{error}\r\n")
                await websocket.send_text("\r\n💡 Sugerencias:\r\n")
                await websocket.send_text("   • Verifica que el usuario y contraseña sean correctos\r\n")
                await websocket.send_text("   • Asegúrate de que el servidor SSH esté accesible\r\n")
                await websocket.send_text("   • Verifica el puerto (por defecto: 22)\r\n")
                await websocket.close(code=1011, reason=error)
                return

            await websocket.send_text(f"\r\n✅ Conectado exitosamente a {credential.host}\r\n")
            await websocket.send_text("━" * 60 + "\r\n\r\n")

            await SSHManager.handle_terminal(websocket, session_id, client)
            client = None  # handle_terminal se encarga del cierre

        except WebSocketDisconnect:
            logger.info("WebSocket desconectado para sesión %s", session_id)
        except Exception as e:
            error_msg = f"❌ Error inesperado: {str(e)}"
            logger.error(error_msg, exc_info=True)
            try:
                await websocket.send_text(f"\r\n{error_msg}\r\n")
                await websocket.close(code=1011, reason=str(e))
            except Exception:
                pass
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            await SSHManager._mark_ended(db, session)
            db.close()

    @staticmethod
    async def _mark_ended(db, session) -> None:
        if session is None:
            return
        try:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.error("Error actualizando sesión %s: %s", session.id, e)

    @staticmethod
    async def handle_terminal(websocket: WebSocket, session_id: str, client: paramiko.SSHClient):
        """Manejar terminal interactivo via WebSocket"""
        channel = None
        try:
            # Crear canal SSH
            channel = client.invoke_shell(term='xterm')
            channel.settimeout(0.0)
            
            # Guardar sesión
            active_sessions[session_id] = {"client": client, "channel": channel}
            
            logger.info(f"📡 Terminal SSH iniciado para sesión {session_id}")
            
            # Función para leer del canal SSH y enviar al WebSocket
            async def read_from_ssh():
                try:
                    while True:
                        if channel.recv_ready():
                            data = channel.recv(1024)
                            if not data:
                                break
                            await websocket.send_text(data.decode('utf-8', errors='ignore'))
                        elif channel.closed or channel.exit_status_ready():
                            break
                        await asyncio.sleep(0.01)
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    raise
                except Exception as e:
                    logger.error(f"Error leyendo de SSH ({session_id}): {e}")
            
            # Función para leer del WebSocket y enviar al canal SSH
            async def write_to_ssh():
                while True:
                    data = await websocket.receive_text()
                    try:
                        channel.send(data)
                    except Exception as e:
                        logger.error(f"Error escribiendo a SSH ({session_id}): {e}")
                        break
            
            # Ejecutar ambas tareas y cancelarlas en cuanto una termine
            # (WebSocket desconectado, canal cerrado o error) para no dejar
            # sesiones SSH abiertas en segundo plano.
            tasks = [
                asyncio.ensure_future(read_from_ssh()),
                asyncio.ensure_future(write_to_ssh()),
            ]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            error_msg = f"❌ Error en terminal SSH: {str(e)}"
            logger.error(error_msg)
            try:
                await websocket.send_text(f"\r\n{error_msg}\r\n")
            except Exception:
                pass
        finally:
            if session_id in active_sessions:
                state = active_sessions.pop(session_id)
                try:
                    state["client"].close()
                except Exception:
                    pass
                logger.info(f"🔌 Sesión SSH {session_id} cerrada")
            else:
                # El canal nunca llegó a registrarse: limpiar igualmente.
                try:
                    if channel is not None:
                        channel.close()
                    client.close()
                except Exception:
                    pass
    
    @staticmethod
    def close_session(session_id: str):
        """Cerrar sesión SSH"""
        state = active_sessions.pop(session_id, None)
        if state is None:
            return
        try:
            state["client"].close()
            logger.info(f"🔌 Sesión SSH {session_id} cerrada manualmente")
        except Exception as e:
            logger.error(f"Error cerrando sesión {session_id}: {e}")
