#!/bin/bash

echo "🔐 Gestor de Contraseñas - Setup"
echo "================================"

# Navegar al directorio backend
cd "$(dirname "$0")/backend"

# Verificar si existe .env
if [ ! -f ".env" ]; then
    echo "📝 Creando archivo .env..."
    
    # Generar claves seguras
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Crear archivo .env
    cat > .env << EOF
# Database
DATABASE_URL=sqlite:///./passwords.db

# Security
SECRET_KEY=$SECRET_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Encryption
ENCRYPTION_KEY=$ENCRYPTION_KEY

# App
APP_NAME=Gestor de Contraseñas
DEBUG=True
EOF
    
    echo "✅ Archivo .env creado con claves seguras"
else
    echo "✅ Archivo .env ya existe"
fi

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
    echo "✅ Entorno virtual creado"
fi

# Activar entorno virtual
echo "🔄 Activando entorno virtual..."
source venv/bin/activate

# Instalar dependencias
echo "📥 Instalando dependencias..."
pip install -r requirements.txt --quiet

echo ""
echo "✅ Setup completado!"
echo ""
echo "Para iniciar la aplicación:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  cd app"
echo "  python main.py"
echo ""
echo "O ejecuta: ./start.sh"
