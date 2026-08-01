from database import engine, SessionLocal
from models.models import Base, User, Organization, UserRole
from core.security import get_password_hash, validate_password_requirements


def run_setup(db_name: str, admin_name: str, admin_email: str, admin_password: str, language: str | None = None) -> str:
    is_valid, message = validate_password_requirements(admin_password)
    if not is_valid:
        raise ValueError(message)

    # Check if already configured via the app's own DB
    from config import get_settings
    settings = get_settings()
    try:
        db = SessionLocal()
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first() is not None
        db.close()
        if admin_exists:
            raise ValueError("El sistema ya está configurado")
    except Exception:
        pass

    # Create tables and admin user using the app's own engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        org = Organization(name="Organización Principal")
        db.add(org)
        db.commit()

        admin_user = User(
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            full_name=admin_name,
            role=UserRole.ADMIN,
            organization_id=org.id,
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()

    return "Configuración completada exitosamente"
