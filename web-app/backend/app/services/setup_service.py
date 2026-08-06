from database import engine, SessionLocal
from models.models import Base, User, Organization, UserRole, SystemSetting
from core.security import get_password_hash, validate_password_requirements


def run_setup(
    db_name: str,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    language: str | None = None,
    master_password: str | None = None,
    telegram_bot_token: str | None = None,
) -> str:
    is_valid, message = validate_password_requirements(admin_password)
    if not is_valid:
        raise ValueError(message)

    if master_password:
        master_valid, master_msg = validate_password_requirements(master_password)
        if not master_valid:
            raise ValueError("Contraseña maestra: " + master_msg)

    # Check if already configured via the app's own DB
    admin_exists = False
    try:
        db = SessionLocal()
        try:
            admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first() is not None
        finally:
            db.close()
    except Exception:
        pass
    if admin_exists:
        raise ValueError("El sistema ya está configurado")

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

    if master_password:
        db = SessionLocal()
        try:
            master_row = db.query(SystemSetting).filter(SystemSetting.key == "master_password_hash").first()
            if master_row:
                master_row.value = get_password_hash(master_password)
            else:
                db.add(SystemSetting(key="master_password_hash", value=get_password_hash(master_password)))
            db.commit()
        finally:
            db.close()

    if telegram_bot_token:
        from core.telegram import set_setting
        set_setting("telegram_bot_token", telegram_bot_token.strip())

    return "Configuración completada exitosamente"
