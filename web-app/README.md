# Gestor de Contraseñas Web

Aplicación web moderna para gestión de contraseñas con terminal SSH integrado y control de roles.

## 🚀 Características

- ✅ **Autenticación JWT** - Login seguro con tokens
- ✅ **Multi-usuario** - Sistema de roles (Admin/Usuario)
- ✅ **Gestión de contraseñas** - CRUD completo con encriptación
- ✅ **Terminal SSH integrado** - Conecta directamente a servidores
- ✅ **Control de permisos** - Asigna acceso granular a credenciales
- ✅ **Interfaz moderna** - UI responsive con Tailwind CSS

## 📋 Requisitos

- Python 3.8+
- pip

## 🛠️ Instalación

1. **Navegar al directorio del backend:**
```bash
cd web-app/backend
```

2. **Crear entorno virtual:**
```bash
python -m venv venv
source venv/bin/activate  
```

3. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno:**
```bash
cp .env.example .env
```

Edita `.env` y configura:
- `SECRET_KEY`: Clave secreta para JWT (genera una aleatoria)
- `ENCRYPTION_KEY`: Clave para encriptar contraseñas (genera una aleatoria)

Para generar claves seguras:
```python
import secrets
print(secrets.token_urlsafe(32))
```

## ▶️ Ejecutar la aplicación

```bash
cd app
python main.py
```

O con uvicorn directamente:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La aplicación estará disponible en: **http://localhost:8000**

## 📖 Uso

### 1. Registro
- Accede a http://localhost:8000
- Click en "Registrarse"
- Ingresa tu correo y contraseña
- El primer usuario de una organización será Admin automáticamente

### 2. Login
- Ingresa tu correo y contraseña
- Serás redirigido al dashboard

### 3. Gestionar Contraseñas
- Click en "Contraseñas" en el menú lateral
- Click en "Nueva Contraseña" para agregar credenciales
- Completa: Host, Usuario, Contraseña, Puerto (opcional), Comentario
- Marca "Compartir" si quieres que otros usuarios la vean

### 4. Conectar SSH
- Click en "Terminal SSH"
- Selecciona una credencial
- Se abrirá un terminal interactivo conectado al servidor

### 5. Administración (Solo Admin)
- Click en "Administración"
- Gestiona usuarios y permisos

## 🔐 Seguridad

- Las contraseñas de usuarios se hashean con bcrypt
- Las credenciales guardadas se encriptan con Fernet (symmetric encryption)
- Autenticación con JWT tokens
- HTTPS recomendado en producción

## 📁 Estructura del Proyecto

```
web-app/backend/
├── app/
│   ├── api/              # Endpoints de la API
│   │   ├── auth.py       # Login/Register
│   │   ├── credentials.py # Gestión de contraseñas
│   │   ├── ssh.py        # Conexiones SSH
│   │   └── deps.py       # Dependencies
│   ├── core/             # Utilidades core
│   │   ├── security.py   # JWT, hashing
│   │   ├── encryption.py # Encriptación
│   │   └── ssh_manager.py # SSH handler
│   ├── models/           # Modelos de base de datos
│   │   └── models.py
│   ├── schemas/          # Schemas Pydantic
│   │   └── schemas.py
│   ├── templates/        # Templates HTML
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── passwords.html
│   │   ├── ssh.html
│   │   └── admin.html
│   ├── static/           # Archivos estáticos
│   ├── config.py         # Configuración
│   ├── database.py       # Setup de DB
│   └── main.py           # App principal
├── requirements.txt
└── .env.example
```

## 🌐 API Endpoints

### Autenticación
- `POST /api/auth/register` - Registrar usuario
- `POST /api/auth/login` - Iniciar sesión

### Credenciales
- `GET /api/credentials/` - Listar credenciales
- `POST /api/credentials/` - Crear credencial
- `GET /api/credentials/{id}` - Ver credencial (con contraseña)
- `PUT /api/credentials/{id}` - Actualizar credencial
- `DELETE /api/credentials/{id}` - Eliminar credencial

### Permisos (Admin)
- `POST /api/credentials/{id}/permissions` - Asignar permiso
- `GET /api/credentials/{id}/permissions` - Listar permisos
- `DELETE /api/credentials/{id}/permissions/{user_id}` - Revocar permiso

### SSH
- `POST /api/ssh/connect` - Iniciar conexión SSH
- `WS /api/ssh/terminal/{session_id}` - WebSocket terminal
- `POST /api/ssh/disconnect/{session_id}` - Cerrar sesión

## 🐳 Docker (Opcional)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t password-manager .
docker run -p 8000:8000 -e SECRET_KEY=your-key -e ENCRYPTION_KEY=your-key password-manager
```

## 📝 Notas

- Por defecto usa SQLite (archivo `passwords.db`)
- Para PostgreSQL, cambia `DATABASE_URL` en `.env`
- En producción, usa HTTPS y configura CORS apropiadamente
- El terminal SSH requiere acceso de red a los servidores remotos

## 🤝 Contribuir

Este es un proyecto de código abierto. ¡Las contribuciones son bienvenidas!

## 📄 Licencia

MIT License
