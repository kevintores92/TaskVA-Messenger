import os
import sqlite3
from flask import Flask, request, session, redirect, url_for, render_template, jsonify

USERS_DB = os.path.join(os.path.dirname(__file__), 'users.db')

# --- Create PayPal Checkout Link ---
def create_checkout_session(username, plan_id):
    """
    Returns a PayPal payment URL for the user to subscribe.
    Replace this with actual PayPal integration logic.
    """
    # Example: Use PayPal's subscription API to create a subscription and get approval link
    # For now, return a placeholder URL
    success_url = f"https://yourdomain.com/payment-success?username={username}"
    cancel_url = f"https://yourdomain.com/payment-cancelled"
    paypal_checkout_url = f"https://www.paypal.com/checkoutnow?token=EXAMPLE_TOKEN&success={success_url}&cancel={cancel_url}"
    return paypal_checkout_url

# --- Mark user as active after payment ---
def activate_user_subscription(username):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN subscription_active INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
    c.execute("UPDATE users SET subscription_active=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()

# --- Check subscription status ---
def is_user_subscribed(username):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("SELECT subscription_active FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])
