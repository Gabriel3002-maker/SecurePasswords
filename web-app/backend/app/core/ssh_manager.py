import paramiko
from fastapi import WebSocket
import asyncio
from typing import Dict
from models.models import SSHSession, Credential
from core.encryption import decrypt_password
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Almacenar sesiones SSH activas
active_sessions: Dict[str, paramiko.SSHClient] = {}

class SSHManager:
    """Gestor de conexiones SSH"""
    
    @staticmethod
    async def connect(credential: Credential) -> tuple[paramiko.SSHClient, str]:
        """
        Establecer conexión SSH
        Returns: (client, error_message)
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
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
    async def handle_terminal(websocket: WebSocket, session_id: str, client: paramiko.SSHClient):
        """Manejar terminal interactivo via WebSocket"""
        try:
            # Crear canal SSH
            channel = client.invoke_shell(term='xterm')
            channel.settimeout(0.0)
            
            # Guardar sesión
            active_sessions[session_id] = client
            
            logger.info(f"📡 Terminal SSH iniciado para sesión {session_id}")
            
            # Función para leer del canal SSH y enviar al WebSocket
            async def read_from_ssh():
                try:
                    while True:
                        if channel.recv_ready():
                            data = channel.recv(1024).decode('utf-8', errors='ignore')
                            await websocket.send_text(data)
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Error leyendo de SSH: {e}")
            
            # Función para leer del WebSocket y enviar al canal SSH
            async def write_to_ssh():
                try:
                    while True:
                        data = await websocket.receive_text()
                        channel.send(data)
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Error escribiendo a SSH: {e}")
            
            # Ejecutar ambas tareas concurrentemente
            await asyncio.gather(
                read_from_ssh(),
                write_to_ssh()
            )
            
        except Exception as e:
            error_msg = f"❌ Error en terminal SSH: {str(e)}"
            logger.error(error_msg)
            try:
                await websocket.send_text(f"\r\n{error_msg}\r\n")
            except:
                pass
        finally:
            # Limpiar sesión
            if session_id in active_sessions:
                try:
                    active_sessions[session_id].close()
                except:
                    pass
                del active_sessions[session_id]
                logger.info(f"🔌 Sesión SSH {session_id} cerrada")
    
    @staticmethod
    def close_session(session_id: str):
        """Cerrar sesión SSH"""
        if session_id in active_sessions:
            try:
                active_sessions[session_id].close()
                logger.info(f"🔌 Sesión SSH {session_id} cerrada manualmente")
            except Exception as e:
                logger.error(f"Error cerrando sesión {session_id}: {e}")
            finally:
                del active_sessions[session_id]

