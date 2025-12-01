# 🔐 Gestor de Contraseñas 

Aplicación  construida en Python , SQLite para gestionar contraseñas de manera local y segura. Permite iniciar sesión, guardar múltiples accesos con detalles personalizados,  exportar a Excel, y cerrar sesión.

---

## 🚀 Funcionalidades

-   Registro e inicio de sesión con SQLite
-   CRUD de accesos (host, usuario, contraseña, token, puerto, comentario)
-   Exportación de datos a xlsx
-   Listado por comentarios para mejor identificación
-   Opción para cerrar sesión y volver a login

---

## 🛠️ Requisitos

-   Dockerfile
-   Docker-compose

---

## 📦 Instalación

1. Clona este repositorio:

    ```bash
    git clone https://github.com/tuusuario/gestor-passwords.git
    cd gestor-passwords
    cd web-app


    ```

2. Ahora necesitar levantar el contenedor

    ```bash

    docker compose up -d
    ```

## 📦 Ejecución

1. Luego de levantar correctamente el contendor accede a tu ip:9000:

2. Termina la configuración y pruebalo:

## 📦 Mejoras y Contribuciones

1. Si vas a aportar con alguna mejora trabaja con lowercase y fomateadores

2. Está aplicación esta hecha para ser simple ,  útil y segura.

3. A las personas que usen el software actualmente es gratuito por fa si ven errores  reportenlos al correo para trabajar en los mismos y mejorar la app

## 📦 Documentacion Tecnica

1. Actualmente el backend se esta trabajando con fastapi en localhost:9000/docs tienes la  documentacion de cada endpoint  con Swagger

2. La carpeta principal a trabajar o mejor es web-app alli tenemos el backend y los archivos html

3. Actualmente no contamos con Test por fa si deseas ayudar crear un nuevo fork para aplicar los mismos

