import tkinter as tk
from tkinter import messagebox, filedialog
from database.database import save_password, get_passwords, delete_password, update_password
from config import colors

CURRENT_THEME = colors.CURRENT_THEME  # accedemos como variable global

def abrir_gestor(user_id, email):
    ventana = tk.Tk()
    ventana.title(f"Gestor de {email}")
    ventana.geometry("800x450")
    ventana.configure(bg=CURRENT_THEME["bg"])

    entradas = {}
    campos = ["Host", "Usuario", "Contraseña", "Token", "Puerto", "Comentario"]

    ## NAVBAR / MENÚ SUPERIOR
    menu_bar = tk.Menu(ventana)
    tema_menu = tk.Menu(menu_bar, tearoff=0)
    tema_menu.add_command(label="Tema Claro", command=lambda: cambiar_tema("claro"))
    tema_menu.add_command(label="Tema Oscuro", command=lambda: cambiar_tema("oscuro"))

    menu_bar.add_cascade(label="Tema", menu=tema_menu)
    menu_bar.add_command(label="Cerrar sesión", command=lambda: cerrar_sesion())
    menu_bar.add_command(label="Exportar", command=lambda: exportar_csv(user_id))

    ventana.config(menu=menu_bar)

    ## FRAMES PARA MEJOR DISTRIBUCIÓN
    frame_izquierdo = tk.Frame(ventana, bg=CURRENT_THEME["bg"])
    frame_izquierdo.pack(side="left", fill="both", expand=True, padx=20, pady=20)

    frame_derecho = tk.Frame(ventana, bg=CURRENT_THEME["bg"])
    frame_derecho.pack(side="right", fill="both", expand=True, padx=10, pady=20)

    # CAMPOS
    for i, campo in enumerate(campos):
        tk.Label(frame_izquierdo, text=campo, bg=CURRENT_THEME["bg"], fg=CURRENT_THEME["fg"]).grid(row=i, column=0, sticky="e", pady=5)
        show_char = "*" if campo == "Contraseña" else ""
        entrada = tk.Entry(frame_izquierdo, width=30, show=show_char,
                           bg=CURRENT_THEME["entry_bg"], fg=CURRENT_THEME["entry_fg"],
                           insertbackground=CURRENT_THEME["entry_fg"])
        entrada.grid(row=i, column=1, pady=5)
        entradas[campo] = entrada

    def toggle_password():
        if entradas["Contraseña"].cget('show') == '':
            entradas["Contraseña"].config(show="*")
            btn_toggle.config(text="Mostrar contraseña")
        else:
            entradas["Contraseña"].config(show="")
            btn_toggle.config(text="Ocultar contraseña")

    btn_toggle = tk.Button(frame_izquierdo, text="Mostrar contraseña", command=toggle_password,
                           bg=CURRENT_THEME["button_bg"], fg=CURRENT_THEME["button_fg"])
    btn_toggle.grid(row=2, column=2, padx=10)

    # BOTONES GUARDAR / ELIMINAR
    tk.Button(frame_izquierdo, text="Guardar", command=lambda: guardar(), bg=CURRENT_THEME["button_bg"], fg=CURRENT_THEME["button_fg"]).grid(row=7, column=0, pady=15)
    tk.Button(frame_izquierdo, text="Eliminar", command=lambda: eliminar(), bg=CURRENT_THEME["button_bg"], fg=CURRENT_THEME["button_fg"]).grid(row=7, column=1, pady=15)

    datos_guardados = []

    def cargar_datos():
        lista.delete(0, tk.END)
        nonlocal datos_guardados
        datos_guardados = get_passwords(user_id)
        for d in datos_guardados:
            lista.insert(tk.END, f"{d['comment']} ")

    def limpiar_campos():
        for campo in campos:
            entradas[campo].delete(0, tk.END)

    def guardar():
        datos = {campo: entradas[campo].get() for campo in campos}
        if not datos["Host"] or not datos["Usuario"] or not datos["Contraseña"]:
            messagebox.showwarning("Campos requeridos", "Completa los campos obligatorios.")
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
        else:
            save_password(user_id, datos["Host"], datos["Usuario"], datos["Contraseña"],
                          datos["Token"] or None, puerto_val, datos["Comentario"] or None)
        cargar_datos()
        limpiar_campos()

    def eliminar():
        seleccionado = lista.curselection()
        if not seleccionado:
            messagebox.showwarning("Selecciona", "Selecciona una entrada para eliminar.")
            return
        idx = seleccionado[0]
        delete_password(datos_guardados[idx]["id"])
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

    # LISTBOX
    lista = tk.Listbox(frame_derecho, width=45, bg=CURRENT_THEME["listbox_bg"], fg=CURRENT_THEME["listbox_fg"])
    lista.pack(fill="both", expand=True)
    lista.bind("<<ListboxSelect>>", on_seleccionar)

    # CAMBIAR TEMA DINÁMICAMENTE
    def cambiar_tema(nombre):
        global CURRENT_THEME
        if nombre == "oscuro":
            CURRENT_THEME = colors.DARK_THEME
        else:
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
        messagebox.showinfo("Éxito", f"Datos exportados a {archivo}")

    def cerrar_sesion():
        ventana.destroy()
        from components.auth import login_ui
        login_ui()

    cargar_datos()
    ventana.mainloop()
