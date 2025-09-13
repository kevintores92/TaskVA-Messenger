
"""
Update the messages table in messages.db by pulling up to 10,000 messages from Twilio API.
Deduplicates and inserts only new messages, matching app logic.
"""
import sqlite3
import os
from datetime import datetime, timezone
from dateutil import parser
from twilio.rest import Client


# --- Set credentials and DB path inline ---
DB_PATH = r'C:\Users\admin\Desktop\ACE\Ace Messenger\Messenger\messages.db'
TWILIO_ACCOUNT_SID = "AC01cbd8ec7f05bc98fcc896532479f3b1"
TWILIO_AUTH_TOKEN = "c0c61fb9976f0e3f37bad549551142b5"
TWILIO_NUMBERS = ["+16154549166", "+16158824633", "+16153144957", "+16158824237", "+16158806389"]
DEFAULT_TWILIO_NUMBER = TWILIO_NUMBERS[0] if TWILIO_NUMBERS and TWILIO_NUMBERS[0] else None

def normalize_e164(num):
    s = ''.join(filter(str.isdigit, str(num)))
    if s.startswith('1') and len(s) == 11:
        return '+' + s
    elif len(s) == 10:
        return '+1' + s
    elif str(num).startswith('+'):
        return str(num)
    return str(num)

def normalize_timestamp(ts_str):
    if not ts_str:
        return ""
    try:
        dt = parser.parse(ts_str)
        dt = dt.replace(tzinfo=None)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts_str)[:19]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Ensure messages table exists with correct columns
cur.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    direction TEXT,
    body TEXT,
    timestamp TEXT,
    status TEXT,
    twilio_number TEXT
)''')

# Load existing messages for deduplication
cur.execute('SELECT phone, direction, body FROM messages')
existing = set(cur.fetchall())

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
import sys
import time

inserted = 0
total = 10000
def print_progress(current, total, bar_length=40):
    percent = float(current) / total
    arrow = '-' * int(round(percent * bar_length)-1) + '>'
    spaces = ' ' * (bar_length - len(arrow))
    sys.stdout.write(f"\rProgress: [{arrow}{spaces}] {int(percent*100)}% ({current}/{total})")
    sys.stdout.flush()

for idx, msg in enumerate(client.messages.list(limit=total), 1):
    phone = normalize_e164(msg.to if msg.direction == 'inbound' else msg.from_)
    direction = msg.direction
    body = msg.body or ''
    status = msg.status
    timestamp = normalize_timestamp(str(msg.date_sent))
    twilio_number = msg.to if direction == 'inbound' else msg.from_
    key = (phone, direction, body)
    if key not in existing:
        cur.execute(
            "INSERT INTO messages (phone, direction, body, timestamp, status, twilio_number) VALUES (?, ?, ?, ?, ?, ?)",
            (phone, direction, body, timestamp, status, twilio_number)
        )
        inserted += 1
        print(f"Inserted: {phone} | {direction} | {timestamp} | {body[:40].replace(chr(10),' ')}...")
    if idx % 50 == 0 or idx == total:
        print_progress(idx, total)

print_progress(total, total)
print()
conn.commit()
conn.close()
print(f"Inserted {inserted} new messages into messages table.")