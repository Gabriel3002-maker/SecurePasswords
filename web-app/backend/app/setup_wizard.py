import os
import sys
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Agregar el directorio actual al path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Base
from models.models import User, Organization, UserRole

# Configuración de encriptación
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def setup_wizard():
    print("\n" + "="*50)
    print("🧙‍♂️ ASISTENTE DE CONFIGURACIÓN - GESTOR DE CONTRASEÑAS")
    print("="*50 + "\n")

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    
    # 1. Configuración de Base de Datos
    print("📂 Configuración de Base de Datos")
    print("-" * 30)
    
    current_db = "passwords.db"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    current_db = line.split("///./")[1].strip()
                    break
    
    db_name = input(f"Nombre de la base de datos [{current_db}]: ").strip()
    if not db_name:
        db_name = current_db
    
    if not db_name.endswith(".db"):
        db_name += ".db"
        
    database_url = f"sqlite:///./{db_name}"
    
    # 2. Configuración de Admin
    print("\n👤 Configuración de Administrador")
    print("-" * 30)
    
    # Verificar si ya existe la DB y el admin
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        
        if admin_exists:
            print(f"✅ Ya existe un administrador ({admin_exists.email})")
            change_admin = input("¿Desea crear uno nuevo o resetear? (s/N): ").lower()
            if change_admin != 's':
                print("\n✅ Configuración completada.")
                return

        while True:
            email = input("Email del administrador: ").strip()
            if "@" in email:
                break
            print("❌ Email inválido")
            
        while True:
            password = getpass("Contraseña del administrador: ")
            if len(password) >= 4:
                confirm = getpass("Confirmar contraseña: ")
                if password == confirm:
                    break
                print("❌ Las contraseñas no coinciden")
            else:
                print("❌ La contraseña debe tener al menos 4 caracteres")
                
        full_name = input("Nombre completo (opcional): ").strip()
        
        # Crear organización y usuario
        org = Organization(name="Organización Principal")
        db.add(org)
        db.commit()
        
        admin_user = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            organization_id=org.id,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        print(f"\n✅ Administrador {email} creado exitosamente")
        
    except Exception as e:
        print(f"\n❌ Error durante la configuración: {e}")
        return
    finally:
        db.close()

    # 3. Guardar configuración
    print("\n💾 Guardando configuración...")
    
    # Generar claves si no existen
    import secrets
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
        
    print(f"✅ Configuración guardada en {env_path}")
    print("\n✨ ¡Todo listo! Iniciando aplicación...\n")

if __name__ == "__main__":
    setup_wizard()
