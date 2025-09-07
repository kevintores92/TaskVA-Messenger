import os
import sqlite3
from twilio.rest import Client

TWILIO_MASTER_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_MASTER_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
USERS_DB = os.path.join(os.path.dirname(__file__), 'users.db')

# --- Create Twilio subaccount for a user ---
def create_twilio_subaccount(username):
    client = Client(TWILIO_MASTER_SID, TWILIO_MASTER_TOKEN)
    sub = client.api.accounts.create(friendly_name=f"{username}_subaccount")
    sub_sid = sub.sid
    sub_token = sub.auth_token
    # Store in users.db
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("ALTER TABLE users ADD COLUMN twilio_sid TEXT")
    c.execute("ALTER TABLE users ADD COLUMN twilio_token TEXT")
    c.execute("UPDATE users SET twilio_sid=?, twilio_token=? WHERE username=?", (sub_sid, sub_token, username))
    conn.commit()
    conn.close()
    return sub_sid, sub_token

# --- Get Twilio client for a user ---
def get_user_twilio_client(username):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("SELECT twilio_sid, twilio_token FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and row[1]:
        return Client(row[0], row[1])
    return None

# --- Guide A2P registration (placeholder) ---
def guide_a2p_registration(username):
    # You would use Twilio's TrustHub API here
    # For now, just mark status in users.db
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("ALTER TABLE users ADD COLUMN a2p_status TEXT")
    c.execute("UPDATE users SET a2p_status=? WHERE username=?", ("pending", username))
    conn.commit()
    conn.close()
    return True
