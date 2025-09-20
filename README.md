# 🔐 Gestor de Contraseñas con Tkinter

Aplicación de escritorio construida en Python usando Tkinter y SQLite para gestionar contraseñas de manera local y segura. Permite iniciar sesión, guardar múltiples accesos con detalles personalizados, cambiar el tema (oscuro/claro), exportar a CSV, y cerrar sesión.

---

## 🚀 Funcionalidades

-   Registro e inicio de sesión con SQLite
-   CRUD de accesos (host, usuario, contraseña, token, puerto, comentario)
-   Interfaz gráfica simple con Tkinter
-   Cambio de tema dinámico (claro/oscuro)
-   Exportación de datos a CSV
-   Listado por comentarios para mejor identificación
-   Opción para cerrar sesión y volver a login

---

## 🛠️ Requisitos

-   Python 3.10+
-   Tkinter (ya viene con Python)
-   pip (para instalar dependencias)

---

## 📦 Instalación

1. Clona este repositorio:

    ```bash
    git clone https://github.com/tuusuario/gestor-passwords.git
    cd gestor-passwords

    ```

2. Generar la version dist

    ```bash

    pyinstaller --name "GestorPasswords" --onefile --noconsole \
    --add-data "config/colors.py:config" \
    main.py
    ```

3. No te preocupes en el caso de que no puedas generar el dist en el repo tienes un carpeta dist solo descarga el proyecto y copia el dist en ruta que desea y ejecuta

## 📦 Ejecución

1. Al principio te mostrara un login solo registrate ya que sera tu contraseña maestra:

2. Puedes disfrutralo :

## 📦 Mejoras y Contribuciones

1. Si vas a aportar con alguna mejora
   trabaja con lowercase y fomateadores

2. Está aplicación esta hecha para ser simple , útil y segura.
