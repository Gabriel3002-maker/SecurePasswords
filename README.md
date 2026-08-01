# 🔐 SecurePasswords

Gestor de contraseñas web con terminal SSH integrado, bot de Telegram y recuperación por código.

## Características

- **Asistente de configuración** — wizard de 2 pasos con selección de idioma (es/en/pt) en vivo
- **Contraseña maestra** — hasheada con bcrypt, recuperable por Telegram
- **Autenticación JWT** — login seguro con tokens y control de roles (Admin / Operador)
- **Gestión de credenciales** — CRUD completo con encriptación Fernet
- **Terminal SSH** — conexión interactiva a servidores remotos desde el navegador
- **Bot de Telegram** — avisos de inicio de sesión y recuperación de maestra por código
- **i18n** — español, inglés y portugués con traducción dinámica
- **Docker** — despliegue con un solo comando

## Requisitos

- Python 3.10+ (si ejecutas sin Docker)
- Docker + Docker Compose (recomendado)
- Bot de Telegram (opcional, creado desde [@BotFather](https://t.me/BotFather))

## Instalación rápida

```bash
git clone https://github.com/Gabriel3002-maker/SecurePasswords.git
cd SecurePasswords/web-app
docker compose up -d --build
```

Abre **http://localhost:9000** y completa el asistente de configuración.

## Asistente de configuración (setup wizard)

### Paso 1 — Idioma y contraseña maestra
Selecciona español 🇪🇸, inglés 🇬🇧 o portugués 🇧🇷. La interfaz se traduce en vivo.
Establece la contraseña maestra que protege todas las credenciales.

### Paso 2 — Administrador y servicios
- Crea el usuario administrador (nombre, correo, contraseña)
- Token del bot de Telegram (opcional) — desde [@BotFather](https://t.me/BotFather)

## Bot de Telegram

Una vez configurado el token, el bot se vincula escribiendo `/start` en Telegram.

| Función | Descripción |
|---------|-------------|
| Avisos de sesión | Cada login envía: correo, hora y IP |
| Recuperación de maestra | Código de 6 caracteres enviado por Telegram (válido 10 min) |

La página de recuperación está disponible en `/recovery` (enlace en el login).

## Desarrollo sin Docker

```bash
cd web-app/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # editar SECRET_KEY y ENCRYPTION_KEY
cd app && python main.py
```

## Estructura del proyecto

```
SecurePasswords/
├── web-app/
│   ├── docker-compose.yml
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── auth.py          # Login / registro
│   │   │   │   ├── credentials.py   # CRUD credenciales
│   │   │   │   ├── ssh.py           # Conexiones SSH + terminal
│   │   │   │   ├── admin.py         # Gestión de usuarios
│   │   │   │   ├── setup.py         # Asistente de configuración
│   │   │   │   └── recovery.py      # Recuperación de maestra
│   │   │   ├── core/
│   │   │   │   ├── security.py      # JWT, hashing bcrypt
│   │   │   │   ├── encryption.py    # Encriptación Fernet
│   │   │   │   ├── ssh_manager.py   # Handler SSH + WebSocket
│   │   │   │   ├── i18n.py          # Traducciones es/en/pt
│   │   │   │   └── telegram.py      # Bot Telegram (polling)
│   │   │   ├── models/
│   │   │   │   └── models.py        # User, Credential, SystemSetting, RecoveryCode
│   │   │   ├── services/
│   │   │   │   └── setup_service.py # Lógica del asistente
│   │   │   ├── templates/
│   │   │   │   ├── layout.html      # Layout base + i18n
│   │   │   │   ├── login.html
│   │   │   │   ├── setup.html       # Asistente de configuración
│   │   │   │   ├── recovery.html    # Recuperación de maestra
│   │   │   │   ├── dashboard.html
│   │   │   │   ├── passwords.html
│   │   │   │   ├── ssh.html
│   │   │   │   └── admin.html
│   │   │   ├── main.py              # App FastAPI + middleware
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── data/                        # DB + SSH keys (no commitear)
├── tests/                           # Suite de pruebas
├── docs/                            # GitHub Pages
└── README.md
```

## API (resumen)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/setup` | Configuración inicial (asistente) |
| POST | `/api/auth/login` | Iniciar sesión |
| GET/POST | `/api/credentials/` | Listar / crear credenciales |
| PUT/DELETE | `/api/credentials/{id}` | Actualizar / eliminar |
| POST | `/api/ssh/connect` | Conectar a servidor SSH |
| WS | `/api/ssh/terminal/{id}` | Terminal SSH interactiva |
| POST | `/api/recovery/request` | Solicitar código por Telegram |
| POST | `/api/recovery/confirm` | Restablecer maestra con código |

## Seguridad

- Contraseñas hasheadas con bcrypt
- Credenciales encriptadas con Fernet
- JWT con expiración configurable
- CSRF protection (cookie + header)
- Terminal SSH con `websocket.accept()` y limpieza de recursos
- Contraseña maestra recuperable solo por Telegram vinculado

## Versión

**v1.0.3** — Setup wizard i18n, Telegram bot, recuperación de maestra, terminal SSH.

## Licencia

MIT
