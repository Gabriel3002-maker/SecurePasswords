from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from database import init_db, SessionLocal
from api import auth, credentials, ssh, admin
from config import get_settings
from core.security import decode_token
from models.models import User, UserRole
from sqlalchemy.exc import OperationalError
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Crear aplicación FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Gestor de contraseñas web con SSH integrado y control de roles",
    version="1.0.0"
)

# CORS (permitir requests desde frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    # Rutas permitidas sin configuración
    allowed_paths = ["/setup", "/api/setup", "/static"]
    
    # Verificar si existe configuración (variables de entorno)
    env_configured = os.getenv("SECRET_KEY") is not None and os.getenv("DATABASE_URL") is not None
    
    # Verificar si existe admin (Configuración completa)
    admin_exists = False
    if env_configured:
        try:
            db = SessionLocal()
            # Verificar si la tabla existe y si hay admin
            try:
                admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first() is not None
            except Exception:
                # Si la tabla no existe, no está configurado
                pass
            finally:
                db.close()
        except Exception:
            pass

    is_configured = env_configured and admin_exists
    
    if not is_configured:
        # Si no está configurado, permitir solo rutas de setup y estáticos
        if request.url.path == "/setup" or request.url.path.startswith("/api/setup") or request.url.path.startswith("/static"):
            return await call_next(request)
        # Redirigir todo lo demás a /setup
        return RedirectResponse(url="/setup")
    
    # Si ya está configurado, bloquear acceso a /setup
    if is_configured and (request.url.path == "/setup" or request.url.path.startswith("/api/setup")):
         return RedirectResponse(url="/")
         
    return await call_next(request)

# Dependencia para obtener usuario desde cookie
async def get_current_user_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
        
    payload = decode_token(token)
    if payload:
        payload["id"] = payload.get("sub")
    return payload

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
    logger.info(f"🌐 Accede a: http://localhost:8000")

# Ruta de Setup
@app.get("/setup")
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", {"request": request})

# Ruta principal - Página de login
@app.get("/")
async def home(request: Request):
    # Si ya tiene cookie válida, redirigir a dashboard
    user = await get_current_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", {"request": request})

# Ruta del dashboard
@app.get("/dashboard")
async def dashboard(request: Request):
    user = await get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

# Ruta de gestión de contraseñas
@app.get("/passwords")
async def passwords(request: Request):
    user = await get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("passwords.html", {"request": request, "user": user})

# Ruta de terminal SSH
@app.get("/ssh")
async def ssh_page(request: Request):
    user = await get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("ssh.html", {"request": request, "user": user})

# Ruta de administración (solo admin)
@app.get("/admin")
async def admin(request: Request):
    user = await get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/")
    
    if user.get("role") != "admin":
        return RedirectResponse(url="/dashboard")
        
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

