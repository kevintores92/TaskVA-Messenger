import sqlite3
import os
from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

USERS_DB = os.path.join(os.path.dirname(__file__), 'users.db')

# --- User DB setup ---
def init_users_db():
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT,
        password TEXT,
        active INTEGER DEFAULT 1
    )''')
    conn.commit()
    conn.close()

init_users_db()

# --- Registration route ---
def register_user(username, email, password):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                  (username, email, generate_password_hash(password)))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

# --- Authentication route ---
def authenticate_user(username, password):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=? AND active=1", (username,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[0], password):
        return True
    return False

# --- Get user info ---
def get_user(username):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("SELECT id, username, email FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    return user
