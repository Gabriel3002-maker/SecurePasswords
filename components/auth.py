import tkinter as tk
from tkinter import messagebox
from database.database import create_tables, register_user, authenticate_user
from components.gestor_password import abrir_gestor
from config import colors

def login_ui():
    create_tables()
    
    # Usar el tema actual
    THEME = colors.CURRENT_THEME

    def login():
        email = entry_email.get()
        password = entry_password.get()
        if not email or not password:
            messagebox.showwarning("Campos vacíos", "Por favor completa todos los campos")
            return
        user_id = authenticate_user(email, password)
        if user_id:
            root.destroy()
            abrir_gestor(user_id, email)
        else:
            messagebox.showerror("Error", "Credenciales incorrectas")

    def register():
        email = entry_email.get()
        password = entry_password.get()
        if not email or not password:
            messagebox.showwarning("Campos vacíos", "Por favor completa todos los campos")
            return
        if register_user(email, password):
            messagebox.showinfo("Registrado", "Usuario registrado correctamente")
        else:
            messagebox.showwarning("Error", "El correo ya está en uso")

    root = tk.Tk()
    root.title("Gestor de Contraseñas - Login")
    root.geometry("500x600")
    root.configure(bg=THEME["bg"])
    root.resizable(False, False)

    # Frame principal centrado con padding
    main_frame = tk.Frame(root, bg=THEME["bg"])
    main_frame.place(relx=0.5, rely=0.5, anchor="center")

    # Título principal con estilo
    title_label = tk.Label(
        main_frame, 
        text="🔐 Gestor de Contraseñas",
        font=("Segoe UI", 24, "bold"),
        bg=THEME["bg"],
        fg=THEME.get("title_fg", THEME["fg"])
    )
    title_label.pack(pady=(0, 10))

    # Subtítulo
    subtitle_label = tk.Label(
        main_frame,
        text="Protege tus credenciales de forma segura",
        font=("Segoe UI", 10),
        bg=THEME["bg"],
        fg=THEME["fg"]
    )
    subtitle_label.pack(pady=(0, 40))

    # Frame para campos de entrada
    fields_frame = tk.Frame(main_frame, bg=THEME["bg"])
    fields_frame.pack(pady=10)

    # Campo de correo
    tk.Label(
        fields_frame,
        text="Correo electrónico",
        font=("Segoe UI", 11, "bold"),
        bg=THEME["bg"],
        fg=THEME["fg"],
        anchor="w"
    ).grid(row=0, column=0, sticky="w", pady=(0, 5))
    
    entry_email = tk.Entry(
        fields_frame,
        width=35,
        font=("Segoe UI", 11),
        bg=THEME["entry_bg"],
        fg=THEME["entry_fg"],
        insertbackground=THEME["entry_fg"],
        relief="flat",
        bd=2,
        highlightthickness=2,
        highlightbackground=THEME.get("border", THEME["entry_bg"]),
        highlightcolor=THEME.get("accent", THEME["button_bg"])
    )
    entry_email.grid(row=1, column=0, pady=(0, 20), ipady=8, ipadx=5)

    # Campo de contraseña
    tk.Label(
        fields_frame,
        text="Contraseña",
        font=("Segoe UI", 11, "bold"),
        bg=THEME["bg"],
        fg=THEME["fg"],
        anchor="w"
    ).grid(row=2, column=0, sticky="w", pady=(0, 5))
    
    entry_password = tk.Entry(
        fields_frame,
        width=35,
        show="●",
        font=("Segoe UI", 11),
        bg=THEME["entry_bg"],
        fg=THEME["entry_fg"],
        insertbackground=THEME["entry_fg"],
        relief="flat",
        bd=2,
        highlightthickness=2,
        highlightbackground=THEME.get("border", THEME["entry_bg"]),
        highlightcolor=THEME.get("accent", THEME["button_bg"])
    )
    entry_password.grid(row=3, column=0, pady=(0, 30), ipady=8, ipadx=5)

    # Frame para botones
    buttons_frame = tk.Frame(main_frame, bg=THEME["bg"])
    buttons_frame.pack(pady=10)

    # Botón de login (primario)
    btn_login = tk.Button(
        buttons_frame,
        text="Iniciar Sesión",
        command=login,
        font=("Segoe UI", 12, "bold"),
        bg=THEME.get("button_success_bg", THEME["button_bg"]),
        fg=THEME["button_fg"],
        relief="flat",
        bd=0,
        padx=40,
        pady=12,
        cursor="hand2",
        activebackground=THEME.get("accent", THEME["button_bg"]),
        activeforeground=THEME["button_fg"]
    )
    btn_login.pack(pady=(0, 15))

    # Botón de registro (secundario)
    btn_register = tk.Button(
        buttons_frame,
        text="Crear Cuenta Nueva",
        command=register,
        font=("Segoe UI", 11),
        bg=THEME.get("button_secondary_bg", THEME["button_bg"]),
        fg=THEME["button_fg"],
        relief="flat",
        bd=0,
        padx=40,
        pady=10,
        cursor="hand2",
        activebackground=THEME.get("border", THEME["button_bg"]),
        activeforeground=THEME["button_fg"]
    )
    btn_register.pack()

    # Footer
    footer_label = tk.Label(
        main_frame,
        text="© 2025 Gestor de Contraseñas Seguro",
        font=("Segoe UI", 8),
        bg=THEME["bg"],
        fg=THEME.get("border", THEME["fg"])
    )
    footer_label.pack(pady=(40, 0))

    # Bind Enter key para login rápido
    entry_email.bind("<Return>", lambda e: entry_password.focus())
    entry_password.bind("<Return>", lambda e: login())

    root.mainloop()
