# Gestor de Contraseñas Web

Aplicación web para gestión de contraseñas con terminal SSH integrado, bot de Telegram y recuperación por código.

## Características

- ✅ **Asistente de configuración** — wizard de 2 pasos con idioma es/en/pt
- ✅ **Contraseña maestra** — hasheada con bcrypt, recuperable por Telegram
- ✅ **Autenticación JWT** — tokens con roles Admin/Operador
- ✅ **Credenciales** — CRUD con encriptación Fernet
- ✅ **Terminal SSH** — conexión interactiva vía WebSocket
- ✅ **Bot Telegram** — avisos de login y recuperación de maestra
- ✅ **i18n** — español, inglés, portugués con traducción en vivo
- ✅ **Docker** — despliegue con un solo comando

## Requisitos

- Python 3.10+ (sin Docker)
- Docker + Docker Compose (recomendado)
- Bot de Telegram (opcional)

## Instalación con Docker

```bash
docker compose up -d --build
```

Abre **http://localhost:9000**. El asistente de configuración guía los primeros pasos.

### Variables de entorno (`backend/.env`)

| Variable | Requerido | Descripción |
|----------|-----------|-------------|
| `SECRET_KEY` | Sí | Clave secreta para JWT |
| `ENCRYPTION_KEY` | Sí | Clave para encriptar credenciales |
| `DATABASE_URL` | Sí | Ruta de la BD SQLite |
| `COOKIE_SECURE` | No | `True` solo si sirves la app por HTTPS. En HTTP plano debe ser `False` (por defecto), o el navegador descarta las cookies de sesión y el login vuelve a la pantalla de inicio. |
| `TELEGRAM_BOT_TOKEN` | No | Token del bot (también configurable en el wizard) |

## Instalación sin Docker

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # editar variables
cd app && python main.py
```

## Asistente de configuración

Al acceder por primera vez, el wizard guía en 2 pasos:

**Paso 1** — Idioma (es/en/pt) y contraseña maestra
**Paso 2** — Usuario administrador + token de Telegram (opcional)

## Bot de Telegram

1. Crea el bot en [@BotFather](https://t.me/BotFather) y copia el token
2. Configúralo en el wizard o en `TELEGRAM_BOT_TOKEN` del `.env`
3. En Telegram, busca tu bot y escribe `/start` para vincular el chat

| Función | Descripción |
|---------|-------------|
| Avisos de sesión | Notificación con correo, hora e IP en cada login |
| Recuperación maestra | Código de 6 caracteres por Telegram (válido 10 min) |

La página de recuperación está en `/recovery` (enlace visible en el login).

## Estructura

```
backend/app/
├── api/
│   ├── auth.py           # Login / registro
│   ├── credentials.py    # CRUD credenciales
│   ├── ssh.py            # SSH + terminal WebSocket
│   ├── admin.py          # Gestión de usuarios (admin)
│   ├── setup.py          # Asistente de configuración
│   └── recovery.py       # Recuperación de maestra
├── core/
│   ├── security.py       # JWT, hashing bcrypt
│   ├── encryption.py     # Encriptación Fernet
│   ├── ssh_manager.py    # Handler SSH
│   ├── i18n.py           # Traducciones es/en/pt
│   └── telegram.py       # Bot Telegram (polling)
├── models/
│   └── models.py         # User, Credential, SystemSetting, RecoveryCode
├── services/
│   └── setup_service.py  # Lógica del wizard
├── templates/
│   ├── layout.html       # Layout base + i18n client-side
│   ├── login.html
│   ├── setup.html        # Asistente de configuración
│   ├── recovery.html     # Recuperación de maestra
│   ├── dashboard.html
│   ├── passwords.html
│   ├── ssh.html
│   └── admin.html
├── main.py
├── config.py
└── database.py
```

## Endpoints de la API

### Autenticación
- `POST /api/auth/login` — Iniciar sesión
- `POST /api/auth/register` — Registrar usuario (solo admin)

### Configuración
- `POST /api/setup` — Configuración inicial (asistente)

### Credenciales
- `GET /api/credentials/` — Listar credenciales
- `POST /api/credentials/` — Crear credencial
- `GET /api/credentials/{id}` — Ver credencial (con contraseña encriptada)
- `PUT /api/credentials/{id}` — Actualizar
- `DELETE /api/credentials/{id}` — Eliminar

### Permisos (Admin)
- `POST /api/credentials/{id}/permissions` — Asignar permiso
- `GET /api/credentials/{id}/permissions` — Listar permisos
- `DELETE /api/credentials/{id}/permissions/{user_id}` — Revocar

### SSH
- `POST /api/ssh/connect` — Iniciar conexión SSH
- `WS /api/ssh/terminal/{session_id}` — Terminal WebSocket
- `POST /api/ssh/disconnect/{session_id}` — Cerrar sesión

### Recuperación
- `POST /api/recovery/request` — Solicitar código por Telegram
- `POST /api/recovery/confirm` — Restablecer maestra con código

### Utilidades
- `GET /api/i18n/translations?lang=es` — Traducciones
- `GET /health` — Health check

## Seguridad

- Contraseñas de usuario hasheadas con bcrypt
- Credenciales encriptadas con Fernet (AES-CBC)
- JWT con expiración configurable
- CSRF protection en POST/PUT/DELETE
- Terminal SSH con `websocket.accept()` y limpieza de recursos
- Recuperación de maestra solo por Telegram vinculado
- Lease de polling para evitar duplicidad en múltiples workers

## Tests

```bash
cd web-app/backend
python -m pytest tests/ -q
```

## Versión

**v1.0.3** — Setup wizard i18n, Telegram bot, recuperación de maestra, terminal SSH.

## Licencia

MIT
