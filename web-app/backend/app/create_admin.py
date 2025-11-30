import os
import sys
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Base
from models.models import User, Organization, UserRole
from config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def create_admin():
    print("\n" + "="*50)
    print("👤 CREAR ADMINISTRADOR MANUALMENTE")
    print("="*50 + "\n")
    
    settings = get_settings()
    database_url = settings.database_url
    
    if not database_url:
        print("❌ No se encontró configuración de base de datos (DATABASE_URL)")
        return

    print(f"📂 Base de datos: {database_url}")
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    try:
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        
        # Check if admin exists
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if admin_exists:
            print(f"⚠️ Ya existe un administrador: {admin_exists.email}")
            if input("¿Crear otro admin? (s/N): ").lower() != 's':
                return

        # Get details
        while True:
            email = input("Email: ").strip()
            if "@" in email:
                break
            print("❌ Email inválido")
            
        while True:
            password = getpass("Contraseña: ")
            if len(password) >= 4:
                confirm = getpass("Confirmar contraseña: ")
                if password == confirm:
                    break
                print("❌ Las contraseñas no coinciden")
            else:
                print("❌ La contraseña debe tener al menos 4 caracteres")
                
        full_name = input("Nombre completo: ").strip()
        
        # Get or create organization
        org = db.query(Organization).first()
        if not org:
            org = Organization(name="Organización Principal")
            db.add(org)
            db.commit()
            print("✅ Organización principal creada")
            
        # Create user
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            organization_id=org.id,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        print(f"\n✅ Administrador {email} creado exitosamente")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
