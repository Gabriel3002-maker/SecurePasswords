from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from database import init_db, SessionLocal
from api import auth, credentials, ssh, admin
from config import get_settings
from core.security import decode_token
from models.models import User, UserRole
from sqlalchemy.orm import Session
import os
import logging
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Gestor de contraseñas web con SSH integrado y control de roles",
    version="1.0.3"
)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next: Callable) -> JSONResponse:
    if request.method in ("POST", "PUT", "DELETE"):
        path = request.url.path
        skip_paths = ("/static", "/api/setup", "/api/auth/", "/health", "/favicon")
        if not any(path.startswith(p) for p in skip_paths):
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("X-CSRF-Token")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token inválido"}
                )
    return await call_next(request)

# CORS (restringido a orígenes conocidos en producción)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:9000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

# Obtener directorio base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Montar archivos estáticos y templates
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)

# Incluir routers de API
app.include_router(auth.router, prefix="/api")
app.include_router(credentials.router, prefix="/api")
app.include_router(ssh.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

# Importar router de setup (lazy import para evitar circular dependencies si fuera el caso)
from api import setup
app.include_router(setup.router, prefix="/api")

# Middleware para verificar configuración
@app.middleware("http")
async def check_configuration(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path == "/health":
        return await call_next(request)

    env_configured = os.getenv("SECRET_KEY") is not None and os.getenv("DATABASE_URL") is not None
    admin_exists = False

    if env_configured:
        try:
            db = SessionLocal()
            try:
                admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first() is not None
            except Exception:
                pass
            finally:
                db.close()
        except Exception:
            pass

    is_configured = env_configured and admin_exists

    if not is_configured and request.url.path not in {"/setup"} and not request.url.path.startswith("/api/setup") and not request.url.path.startswith("/api/auth/"):
        return RedirectResponse(url="/setup")

    if is_configured and request.url.path in {"/setup"}:
        return RedirectResponse(url="/")

    return await call_next(request)

# Dependencia para obtener usuario desde cookie
def get_current_user_from_cookie(request: Request, db: Optional[Session] = None):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
        
    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    # Verify the user still exists in the database
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        payload["id"] = user_id
        payload["email"] = user.email
        payload["role"] = user.role.value
        payload["org_id"] = user.organization_id
        payload["full_name"] = user.full_name
        return payload
    finally:
        if own_session:
            db.close()

# Inicializar base de datos al arrancar
@app.on_event("startup")
def on_startup():
    # Solo inicializar si está configurado
    # env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    # if os.path.exists(env_path):
    if os.getenv("DATABASE_URL"):
        try:
            init_db()
            logger.info("✅ Base de datos inicializada")
        except Exception as e:
            # Ignorar error si la tabla ya existe (race condition en workers)
            if "already exists" in str(e):
                logger.info("✅ Base de datos ya estaba inicializada")
            else:
                logger.error(f"❌ Error inicializando DB: {e}")
    
    logger.info(f"🚀 {settings.app_name} iniciado correctamente")
    logger.info(f"📂 Directorio de trabajo: {os.getcwd()}")
    logger.info(f"🌐 Accede a: http://localhost:9000")

def _template_params(request: Request, user: dict | None = None, active_page: str = "") -> dict:
    """Construir contexto común para todas las plantillas."""
    csrf = request.cookies.get("csrf_token", "")
    return {
        "request": request,
        "user": user,
        "active_page": active_page,
        "csrf_token": csrf,
    }

def _require_auth(request: Request) -> dict | None:
    user = get_current_user_from_cookie(request)
    if not user:
        return None
    return user

@app.get("/setup")
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", _template_params(request))

@app.get("/")
async def home(request: Request):
    user = _require_auth(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", _template_params(request))

@app.get("/dashboard")
async def dashboard(request: Request):
    user = _require_auth(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("dashboard.html", _template_params(request, user, "dashboard"))

@app.get("/passwords")
async def passwords(request: Request):
    user = _require_auth(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("passwords.html", _template_params(request, user, "passwords"))

@app.get("/ssh")
async def ssh_page(request: Request):
    user = _require_auth(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("ssh.html", _template_params(request, user, "ssh"))

@app.get("/admin")
async def admin(request: Request):
    user = _require_auth(request)
    if not user:
        return RedirectResponse(url="/")
    if user.get("role") != "admin":
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("admin.html", _template_params(request, user, "admin"))

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

