import pyperclip
import tkinter as tk
from tkinter import messagebox
import json
import os
from datetime import datetime


def copy_to_clipboard(text: str):
    """Copy text to clipboard"""
    try:
        pyperclip.copy(text)
        show_message("Success", "Copied to clipboard!")
    except Exception as e:
        show_message("Error", f"Failed to copy to clipboard: {e}")


def show_message(title: str, message: str, message_type: str = "info"):
    """Show a message box"""
    if message_type.lower() == "error":
        messagebox.showerror(title, message)
    elif message_type.lower() == "warning":
        messagebox.showwarning(title, message)
    else:
        messagebox.showinfo(title, message)


def validate_password_strength(password: str, min_length: int = 8) -> bool:
    """Basic password strength validation"""
    if len(password) < min_length:
        return False

    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)

    return has_lower and has_upper and has_digit


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp


def export_to_json(data: list, filename: str) -> bool:
    """Export data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        show_message("Export Error", f"Failed to export data: {e}")
        return False


def import_from_json(filename: str) -> list:
    """Import data from JSON file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        show_message("Import Error", f"Failed to import data: {e}")
        return []


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = getattr(__import__('sys'), '_MEIPASS')
    except:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def center_window(window: tk.Tk, width: int, height: int):
    """Center a tkinter window on screen"""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    window.geometry(f"{width}x{height}+{x}+{y}")


def create_tooltip(widget, text: str):
    """Create a tooltip for a widget"""
    def show_tooltip(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

        label = tk.Label(tooltip, text=text, background="#ffffe0",
                         relief="solid", borderwidth=1)
        label.pack()

        def hide_tooltip():
            tooltip.destroy()

        widget.tooltip = tooltip
        widget.after(2000, hide_tooltip)  # Auto-hide after 2 seconds

    def hide_tooltip(event):
        if hasattr(widget, 'tooltip'):
            widget.tooltip.destroy()
            delattr(widget, 'tooltip')

    widget.bind("<Enter>", show_tooltip)
    widget.bind("<Leave>", hide_tooltip)


def generate_backup_filename() -> str:
    """Generate a backup filename with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"passwords_backup_{timestamp}.json"
