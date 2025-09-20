import tkinter as tk
from tkinter import messagebox
from database.database import create_tables, register_user, authenticate_user
from  components.gestor_password import abrir_gestor

def login_ui():
    create_tables()

    def login():
        email = entry_email.get()
        password = entry_password.get()
        user_id = authenticate_user(email, password)
        if user_id:
            root.destroy()
            abrir_gestor(user_id, email)
        else:
            messagebox.showerror("Error", "Credenciales incorrectas")

    def register():
        email = entry_email.get()
        password = entry_password.get()
        if register_user(email, password):
            messagebox.showinfo("Registrado", "Usuario registrado correctamente")
        else:
            messagebox.showwarning("Error", "El correo ya está en uso")

    root = tk.Tk()
    root.title("Login")
    root.geometry("300x200")

    tk.Label(root, text="Correo:").pack(pady=5)
    entry_email = tk.Entry(root)
    entry_email.pack()

    tk.Label(root, text="Contraseña:").pack(pady=5)
    entry_password = tk.Entry(root, show="*")
    entry_password.pack()

    tk.Button(root, text="Iniciar sesión", command=login).pack(pady=10)
    tk.Button(root, text="Registrarse", command=register).pack()

    root.mainloop()
