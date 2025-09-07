import os
import sqlite3
import stripe
from flask import Flask, request, session, redirect, url_for, render_template, jsonify

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
stripe.api_key = STRIPE_SECRET_KEY
USERS_DB = os.path.join(os.path.dirname(__file__), 'users.db')

# --- Create Stripe Checkout Session ---
def create_checkout_session(username, price_id):
    session_obj = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        success_url='https://yourdomain.com/payment-success?session_id={CHECKOUT_SESSION_ID}',
        cancel_url='https://yourdomain.com/payment-cancelled',
        metadata={'username': username}
    )
    return session_obj.url

# --- Mark user as active after payment ---
def activate_user_subscription(username):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("ALTER TABLE users ADD COLUMN subscription_active INTEGER DEFAULT 0")
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
