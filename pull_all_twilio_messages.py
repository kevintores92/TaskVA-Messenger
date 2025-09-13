"""
Pull all messages from Twilio (no limit, paginated) and insert unique messages into messages.db.
Deduplicates by (phone, direction, body). Prints progress.
"""
import sqlite3
import os
from datetime import datetime
from dateutil import parser
from twilio.rest import Client

DB_PATH = r'C:\Users\admin\Desktop\ACE\Ace Messenger\Messenger\messages.db'
TWILIO_ACCOUNT_SID = "AC01cbd8ec7f05bc98fcc896532479f3b1"
TWILIO_AUTH_TOKEN = "c0c61fb9976f0e3f37bad549551142b5"
TWILIO_NUMBERS = ["+16154549166", "+16158824633", "+16153144957", "+16158824237", "+16158806389"]
DEFAULT_TWILIO_NUMBER = TWILIO_NUMBERS[0] if TWILIO_NUMBERS and TWILIO_NUMBERS[0] else None

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()


cur.execute('''CREATE TABLE IF NOT EXISTS twilio_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    direction TEXT,
    body TEXT,
    timestamp TEXT,
    status TEXT,
    twilio_number TEXT
)''')
cur.execute('SELECT phone, direction, body FROM twilio_messages')
existing = set(cur.fetchall())

inserted = 0
count = 0
print("Pulling messages from Twilio...")
for msg in client.messages.stream():  # No limit, paginated
    count += 1
    phone = msg.to if msg.direction == 'inbound' else msg.from_
    direction = msg.direction
    body = msg.body or ''
    status = msg.status
    # Format timestamp as 'YYYY MMM DD | h:mm AM/PM'
    if msg.date_sent:
        dt = parser.parse(str(msg.date_sent))
        timestamp = dt.strftime('%Y %b %d | %#I:%M %p')
    else:
        timestamp = ''
    twilio_number = msg.to if direction == 'inbound' else msg.from_
    key = (phone, direction, body)
    if key not in existing:
        cur.execute(
            "INSERT INTO twilio_messages (phone, direction, body, timestamp, status, twilio_number) VALUES (?, ?, ?, ?, ?, ?)",
            (phone, direction, body, timestamp, status, twilio_number)
        )
        inserted += 1
        print(f"Inserted: {phone} | {direction} | {timestamp} | {body[:40].replace(chr(10),' ')}...")
    if count % 100 == 0:
        print(f"Processed {count} messages...")

conn.commit()
conn.close()
print(f"Done. Inserted {inserted} new messages out of {count} fetched.")
