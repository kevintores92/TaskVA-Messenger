import os
import sqlite3
from twilio.rest import Client

TWILIO_MASTER_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_MASTER_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
USERS_DB = os.path.join(os.path.dirname(__file__), 'users.db')

# --- Assign phone number to subaccount ---
def assign_phone_number_to_subaccount(username, area_code="312"):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("SELECT twilio_sid, twilio_token FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0] or not row[1]:
        return None, "Twilio subaccount not found."
    sub_sid, sub_token = row[0], row[1]
    master_client = Client(TWILIO_MASTER_SID, TWILIO_MASTER_TOKEN)
    sub_client = Client(sub_sid, sub_token)
    # Search for available number
    numbers = master_client.available_phone_numbers("US").local.list(area_code=area_code, sms_enabled=True, limit=1)
    if not numbers:
        return None, "No available numbers."
    number = numbers[0].phone_number
    # Buy number for subaccount
    purchased = master_client.incoming_phone_numbers.create(phone_number=number, account_sid=sub_sid)
    # Store number in users.db
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("ALTER TABLE users ADD COLUMN twilio_number TEXT")
    c.execute("UPDATE users SET twilio_number=? WHERE username=?", (number, username))
    conn.commit()
    conn.close()
    return number, None

# --- Get campaign/A2P status ---
def get_a2p_status(username):
    conn = sqlite3.connect(USERS_DB)
    c = conn.cursor()
    c.execute("SELECT a2p_status FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "unknown"
