#!/bin/bash

echo "🚀 Iniciando Gestor de Contraseñas..."
cd "$(dirname "$0")/backend"

# Activar entorno virtual
source venv/bin/activate

# Iniciar aplicación
echo "🚀 Iniciando Gestor de Contraseñas..."
uvicorn main:app --app-dir app --reload --host 0.0.0.0 --port 8000
