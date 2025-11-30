from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
import os
import secrets
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from models.models import Base, User, Organization, UserRole

router = APIRouter(tags=["Setup"])

class SetupRequest(BaseModel):
    db_name: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

@router.post("/setup")
async def run_setup(data: SetupRequest):
    """Ejecutar configuración inicial"""
    
    # Validar nombre de DB
    db_name = data.db_name.strip()
    if not db_name.endswith(".db"):
        db_name += ".db"
        
    # Rutas
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(os.path.dirname(base_dir), ".env")
    
    # Verificar si ya existe .env (seguridad)
    if os.path.exists(env_path):
        # Leer si ya está configurado
        with open(env_path, "r") as f:
            content = f.read()
            if "DATABASE_URL" in content and "SECRET_KEY" in content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El sistema ya está configurado"
                )

    try:
        # 1. Crear Base de Datos y Admin
        database_url = f"sqlite:///./{db_name}"
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        
        try:
            # Crear organización
            org = Organization(name="Organización Principal")
            db.add(org)
            db.commit()
            
            # Crear admin
            admin_user = User(
                email=data.admin_email,
                password_hash=get_password_hash(data.admin_password),
                full_name=data.admin_name,
                role=UserRole.ADMIN,
                organization_id=org.id,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            
        finally:
            db.close()
            
        # 2. Guardar configuración (Solo si no estamos usando variables de entorno)
        if not (os.getenv("SECRET_KEY") and os.getenv("DATABASE_URL")):
            # Generar .env
            secret_key = secrets.token_urlsafe(32)
            encryption_key = secrets.token_urlsafe(32)
            
            env_content = f"""DATABASE_URL={database_url}
SECRET_KEY={secret_key}
ENCRYPTION_KEY={encryption_key}
ACCESS_TOKEN_EXPIRE_MINUTES=60
APP_NAME="Gestor de Contraseñas"
DEBUG=True
"""
            
            with open(env_path, "w") as f:
                f.write(env_content)
        else:
            print("ℹ️ Usando variables de entorno existentes, saltando creación de .env")
            
        return {"message": "Configuración completada exitosamente"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la configuración: {str(e)}"
        )
