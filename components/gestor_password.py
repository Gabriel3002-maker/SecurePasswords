import tkinter as tk
from tkinter import messagebox, filedialog
from database.database import save_password, get_passwords, delete_password, update_password
from config import colors

CURRENT_THEME = colors.CURRENT_THEME  # accedemos como variable global

def abrir_gestor(user_id, email):
    ventana = tk.Tk()
    ventana.title(f"🔐 Gestor de Contraseñas - {email}")
    ventana.geometry("1100x650")
    ventana.configure(bg=CURRENT_THEME["bg"])
    ventana.resizable(False, False)

    entradas = {}
    campos = ["Host", "Usuario", "Contraseña", "Token", "Puerto", "Comentario"]

    ## NAVBAR / MENÚ SUPERIOR
    menu_bar = tk.Menu(ventana)
    tema_menu = tk.Menu(menu_bar, tearoff=0)
    tema_menu.add_command(label="☀ Tema Claro", command=lambda: cambiar_tema("claro"))
    tema_menu.add_command(label="☾ Tema Oscuro", command=lambda: cambiar_tema("oscuro"))

    menu_bar.add_cascade(label="⚙ Tema", menu=tema_menu)
    menu_bar.add_command(label="💾 Exportar", command=lambda: exportar_csv(user_id))
    menu_bar.add_command(label="→ Cerrar sesión", command=lambda: cerrar_sesion())

    ventana.config(menu=menu_bar)

    ## FRAMES PARA MEJOR DISTRIBUCIÓN
    # Frame izquierdo - Formulario
    frame_izquierdo = tk.Frame(ventana, bg=CURRENT_THEME["bg"])
    frame_izquierdo.pack(side="left", fill="both", expand=True, padx=30, pady=30)

    # Título del formulario
    tk.Label(
        frame_izquierdo,
        text="Información de Credenciales",
        font=("Segoe UI", 16, "bold"),
        bg=CURRENT_THEME["bg"],
        fg=CURRENT_THEME.get("title_fg", CURRENT_THEME["fg"])
    ).grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky="w")

    # CAMPOS
    for i, campo in enumerate(campos):
        row = i + 1
        tk.Label(
            frame_izquierdo,
            text=campo + ":",
            font=("Segoe UI", 11, "bold"),
            bg=CURRENT_THEME["bg"],
            fg=CURRENT_THEME["fg"]
        ).grid(row=row, column=0, sticky="e", pady=8, padx=(0, 10))
        
        show_char = "●" if campo == "Contraseña" else ""
        entrada = tk.Entry(
            frame_izquierdo,
            width=35,
            show=show_char,
            font=("Segoe UI", 10),
            bg=CURRENT_THEME["entry_bg"],
            fg=CURRENT_THEME["entry_fg"],
            insertbackground=CURRENT_THEME["entry_fg"],
            relief="flat",
            bd=2,
            highlightthickness=2,
            highlightbackground=CURRENT_THEME.get("border", CURRENT_THEME["entry_bg"]),
            highlightcolor=CURRENT_THEME.get("accent", CURRENT_THEME["button_bg"])
        )
        entrada.grid(row=row, column=1, pady=8, ipady=6, ipadx=5)
        entradas[campo] = entrada

    def toggle_password():
        if entradas["Contraseña"].cget('show') == '':
            entradas["Contraseña"].config(show="●")
            btn_toggle.config(text="👁 Mostrar")
        else:
            entradas["Contraseña"].config(show="")
            btn_toggle.config(text="🔒 Ocultar")

    btn_toggle = tk.Button(
        frame_izquierdo,
        text="👁 Mostrar",
        command=toggle_password,
        font=("Segoe UI", 9),
        bg=CURRENT_THEME.get("button_secondary_bg", CURRENT_THEME["button_bg"]),
        fg=CURRENT_THEME["button_fg"],
        relief="flat",
        bd=0,
        padx=12,
        pady=6,
        cursor="hand2"
    )
    btn_toggle.grid(row=3, column=2, padx=10)

    # FRAME PARA BOTONES DE ACCIÓN
    buttons_frame = tk.Frame(frame_izquierdo, bg=CURRENT_THEME["bg"])
    buttons_frame.grid(row=8, column=0, columnspan=3, pady=25)

    # Botón Guardar (verde/éxito)
    tk.Button(
        buttons_frame,
        text="💾 Guardar",
        command=lambda: guardar(),
        font=("Segoe UI", 11, "bold"),
        bg=CURRENT_THEME.get("button_success_bg", CURRENT_THEME["button_bg"]),
        fg=CURRENT_THEME["button_fg"],
        relief="flat",
        bd=0,
        padx=30,
        pady=12,
        cursor="hand2",
        width=12
    ).pack(side="left", padx=10)

    # Botón Eliminar (rojo/peligro)
    tk.Button(
        buttons_frame,
        text="🗑 Eliminar",
        command=lambda: eliminar(),
        font=("Segoe UI", 11, "bold"),
        bg=CURRENT_THEME.get("button_danger_bg", CURRENT_THEME["button_bg"]),
        fg=CURRENT_THEME["button_fg"],
        relief="flat",
        bd=0,
        padx=30,
        pady=12,
        cursor="hand2",
        width=12
    ).pack(side="left", padx=10)

    # Botón Limpiar (secundario)
    tk.Button(
        buttons_frame,
        text="✨ Limpiar",
        command=lambda: limpiar_campos(),
        font=("Segoe UI", 11),
        bg=CURRENT_THEME.get("button_secondary_bg", CURRENT_THEME["button_bg"]),
        fg=CURRENT_THEME["button_fg"],
        relief="flat",
        bd=0,
        padx=30,
        pady=12,
        cursor="hand2",
        width=12
    ).pack(side="left", padx=10)

    # Frame derecho - Lista de contraseñas
    frame_derecho = tk.Frame(ventana, bg=CURRENT_THEME["bg"])
    frame_derecho.pack(side="right", fill="both", expand=True, padx=30, pady=30)

    # Título de la lista
    tk.Label(
        frame_derecho,
        text="Contraseñas Guardadas",
        font=("Segoe UI", 16, "bold"),
        bg=CURRENT_THEME["bg"],
        fg=CURRENT_THEME.get("title_fg", CURRENT_THEME["fg"])
    ).pack(pady=(0, 15))

    # Frame para listbox con scrollbar
    listbox_frame = tk.Frame(frame_derecho, bg=CURRENT_THEME["bg"])
    listbox_frame.pack(fill="both", expand=True)

    # Scrollbar
    scrollbar = tk.Scrollbar(listbox_frame)
    scrollbar.pack(side="right", fill="y")

    datos_guardados = []

    def cargar_datos():
        lista.delete(0, tk.END)
        nonlocal datos_guardados
        datos_guardados = get_passwords(user_id)
        for d in datos_guardados:
            # Formato mejorado para la lista
            display_text = f"📌 {d['comment'] or d['host']} - {d['username']}"
            lista.insert(tk.END, display_text)

    def limpiar_campos():
        for campo in campos:
            entradas[campo].delete(0, tk.END)

    def guardar():
        datos = {campo: entradas[campo].get() for campo in campos}
        if not datos["Host"] or not datos["Usuario"] or not datos["Contraseña"]:
            messagebox.showwarning("Campos requeridos", "Completa Host, Usuario y Contraseña.")
            return
        try:
            puerto_val = int(datos["Puerto"]) if datos["Puerto"] else None
        except ValueError:
            messagebox.showerror("Error", "El campo Puerto debe ser un número.")
            return

        seleccionado = lista.curselection()
        if seleccionado:
            idx = seleccionado[0]
            entry_id = datos_guardados[idx]["id"]
            update_password(entry_id, datos["Host"], datos["Usuario"], datos["Contraseña"],
                            datos["Token"] or None, puerto_val, datos["Comentario"] or None)
            messagebox.showinfo("Actualizado", "Contraseña actualizada correctamente")
        else:
            save_password(user_id, datos["Host"], datos["Usuario"], datos["Contraseña"],
                          datos["Token"] or None, puerto_val, datos["Comentario"] or None)
            messagebox.showinfo("Guardado", "Contraseña guardada correctamente")
        cargar_datos()
        limpiar_campos()

    def eliminar():
        seleccionado = lista.curselection()
        if not seleccionado:
            messagebox.showwarning("Selecciona", "Selecciona una entrada para eliminar.")
            return
        
        # Confirmación antes de eliminar
        if messagebox.askyesno("Confirmar", "¿Estás seguro de eliminar esta contraseña?"):
            idx = seleccionado[0]
            delete_password(datos_guardados[idx]["id"])
            messagebox.showinfo("Eliminado", "Contraseña eliminada correctamente")
            cargar_datos()
            limpiar_campos()

    def on_seleccionar(event):
        seleccionado = lista.curselection()
        if not seleccionado:
            return
        idx = seleccionado[0]
        datos = datos_guardados[idx]
        for campo in campos:
            entradas[campo].delete(0, tk.END)
        entradas["Host"].insert(0, datos["host"])
        entradas["Usuario"].insert(0, datos["username"])
        entradas["Contraseña"].insert(0, datos["password"])
        entradas["Token"].insert(0, datos.get("token") or "")
        entradas["Puerto"].insert(0, str(datos.get("port") or ""))
        entradas["Comentario"].insert(0, datos.get("comment") or "")

    # LISTBOX con estilo mejorado
    lista = tk.Listbox(
        listbox_frame,
        width=50,
        height=22,
        font=("Segoe UI", 10),
        bg=CURRENT_THEME["listbox_bg"],
        fg=CURRENT_THEME["listbox_fg"],
        selectbackground=CURRENT_THEME.get("listbox_select_bg", CURRENT_THEME["button_bg"]),
        selectforeground=CURRENT_THEME.get("listbox_select_fg", CURRENT_THEME["button_fg"]),
        relief="flat",
        bd=2,
        highlightthickness=2,
        highlightbackground=CURRENT_THEME.get("border", CURRENT_THEME["listbox_bg"]),
        highlightcolor=CURRENT_THEME.get("accent", CURRENT_THEME["button_bg"]),
        yscrollcommand=scrollbar.set,
        activestyle="none"
    )
    lista.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=lista.yview)
    lista.bind("<<ListboxSelect>>", on_seleccionar)

    # CAMBIAR TEMA DINÁMICAMENTE
    def cambiar_tema(nombre):
        global CURRENT_THEME
        if nombre == "oscuro":
            colors.CURRENT_THEME = colors.DARK_THEME
            CURRENT_THEME = colors.DARK_THEME
        else:
            colors.CURRENT_THEME = colors.LIGHT_THEME
            CURRENT_THEME = colors.LIGHT_THEME
        ventana.destroy()
        abrir_gestor(user_id, email)

    # EXPORTAR CSV
    def exportar_csv(user_id):
        datos = get_passwords(user_id)
        if not datos:
            messagebox.showinfo("Sin datos", "No hay datos para exportar.")
            return
        archivo = filedialog.asksaveasfilename(defaultextension=".csv",
                                               filetypes=[("CSV files", "*.csv")])
        if not archivo:
            return
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("Host,Usuario,Contraseña,Token,Puerto,Comentario\n")
            for d in datos:
                fila = f"{d['host']},{d['username']},{d['password']},{d.get('token','')},{d.get('port','')},{d.get('comment','')}\n"
                f.write(fila)
        messagebox.showinfo("Éxito", f"Datos exportados a:\n{archivo}")

    def cerrar_sesion():
        if messagebox.askyesno("Cerrar sesión", "¿Deseas cerrar sesión?"):
            ventana.destroy()
            from components.auth import login_ui
            login_ui()

    cargar_datos()
    ventana.mainloop()
