import sqlite3
from cryptography.fernet import Fernet
import os

# ------------------ Cifrado ------------------

def generate_key():
    if not os.path.exists("key.key"):
        key = Fernet.generate_key()
        with open("key.key", "wb") as file:
            file.write(key)

def load_key():
    with open("key.key", "rb") as file:
        return file.read()

generate_key()
fernet = Fernet(load_key())

# ------------------ DB Connection ------------------

conn = sqlite3.connect("passwords.db")
cursor = conn.cursor()

def create_tables():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            host TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            token TEXT,
            port INTEGER,
            comment TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()

# ------------------ Users ------------------

def register_user(email, password):
    encrypted = fernet.encrypt(password.encode())
    try:
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, encrypted))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(email, password):
    cursor.execute("SELECT id, password FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    if row and fernet.decrypt(row[1]).decode() == password:
        return row[0]  # Devuelve user_id
    return None

# ------------------ Passwords ------------------

def save_password(user_id, host, username, password, token=None, port=None, comment=None):
    encrypted = fernet.encrypt(password.encode())
    cursor.execute('''
        INSERT INTO passwords (user_id, host, username, password, token, port, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, host, username, encrypted, token, port, comment))
    conn.commit()

def get_passwords(user_id):
    cursor.execute("SELECT id, host, username, password, token, port, comment FROM passwords WHERE user_id = ?", (user_id,))
    result = cursor.fetchall()
    return [
        {
            "id": row[0],
            "host": row[1],
            "username": row[2],
            "password": fernet.decrypt(row[3]).decode(),
            "token": row[4],
            "port": row[5],
            "comment": row[6],
        }
        for row in result
    ]

def delete_password(entry_id):
    cursor.execute("DELETE FROM passwords WHERE id = ?", (entry_id,))
    conn.commit()

def update_password(id, host, user, password, token, port, comment):
    cursor.execute('''
        UPDATE passwords
        SET host = ?, user = ?, password = ?, token = ?, port = ?, comment = ?
        WHERE id = ?
    ''', (host, user, password, token, port, comment, id))
    conn.commit()
