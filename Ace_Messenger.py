import os, sqlite3, threading, webbrowser, time, csv
from datetime import datetime, timezone, timedelta
from dateutil import parser, tz
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, g
from flask_socketio import SocketIO
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from sms_sender_core import send_sms_batch
# ── CONFIG ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "messages.db")
LEADS_CSV_PATH = os.path.join(BASE_DIR, "Leads.csv")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBERS = os.environ.get("TWILIO_NUMBERS", "").split(",")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
batch_status = {"sent": 0, "total": 0, "running": False}
BATCH_CSV = os.path.join(BASE_DIR, 'Batch.csv')
PORT = 5000
KPIS_DB_PATH = r"C:\Users\admin\Desktop\Ace Holdings\sms_kpis.db"
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "aceholdings_secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Stop flag for batch control
stop_batch = False

TAGS = [
    "Hot", "Nurture", "Drip", "Qualified", "Wrong Number", "Not interested", "DNC"
]
TAG_ICONS = {
    "Hot": "🔥",
    "Nurture": "🌱",
    "Drip": "💧",
    "Qualified": "✅",
    "Wrong Number": "❗",
    "Not interested": "❌",
    "DNC": "📵",
    "No tag": "🏷️"
}

# ── HELPERS ────────────────────────────────────────────────────────
    
def normalize_e164(num):
    s = ''.join(filter(str.isdigit, str(num)))
    if s.startswith('1') and len(s) == 11:
        return '+' + s
    elif len(s) == 10:
        return '+1' + s
    elif num.startswith('+'):
        return num
    return num
def normalize_timestamp(ts_str):
    if not ts_str:
        return ""
    try:
        if "T" in ts_str:
            date_part, time_part = ts_str.split("T")
        elif " " in ts_str:
            date_part, time_part = ts_str.split(" ")
        else:
            # fallback if timestamp is not standard
            return ts_str

        time_part = time_part.split(".")[0]  # remove microseconds
        return f"{date_part} {time_part}"
    except Exception as e:
        print(f"Error normalizing timestamp: {ts_str} -> {e}")
        return ts_str


        # Example before inserting into DB
        raw_ts = message["timestamp"]  # from Twilio API
        normalized_ts = normalize_timestamp(raw_ts)
        message["timestamp"] = normalized_ts

        # Now insert message dict into DB
        db_cursor.execute("""
            INSERT INTO messages (phone, body, timestamp, ...)
            VALUES (?, ?, ?, ...)
        """, (message["phone"], message["body"], message["timestamp"], ...))

def get_caller_id_for_phone(phone):
    phone = normalize_e164(phone)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 1) Latest INBOUND
    c.execute("""
        SELECT twilio_number FROM messages
        WHERE phone=? AND direction='inbound'
              AND twilio_number IS NOT NULL AND twilio_number != ''
        ORDER BY timestamp DESC LIMIT 1
    """, (phone,))
    row = c.fetchone()
    if row and row[0]:
        conn.close()
        return row[0]
    # 2) Latest OUTBOUND
    c.execute("""
        SELECT twilio_number FROM messages
        WHERE phone=? AND direction LIKE 'outbound%%'
              AND twilio_number IS NOT NULL AND twilio_number != ''
        ORDER BY timestamp DESC LIMIT 1
    """, (phone,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    # 3) Default fallback
    return TWILIO_NUMBERS[0]

def remove_drip_assignment(phone):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM contact_drip_assignments WHERE contact_phone=?", (phone,))
    conn.commit()
    conn.close()

def log_message(phone, direction, body, status=None, timestamp=None, twilio_number=None):
    phone = normalize_e164(phone)

    # Ensure timestamp
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    timestamp = normalize_timestamp(timestamp)

    # Fallback Twilio number logic
    if not twilio_number:
        try:
            if request:  # Only valid inside a request context
                if direction == 'inbound':
                    twilio_number = request.form.get("To")
                else:
                    twilio_number = request.form.get("From")
        except RuntimeError:
            # No request context (e.g. background import)
            pass
        if not twilio_number:
            twilio_number = TWILIO_NUMBERS[0]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Duplicate check (ignore timestamp to avoid mismatch problems)
    c.execute("SELECT 1 FROM messages WHERE phone=? AND direction=? AND body=?",
              (phone, direction, body))
    if not c.fetchone():
        c.execute(
            "INSERT INTO messages (phone, direction, body, timestamp, status, twilio_number) VALUES (?, ?, ?, ?, ?, ?)",
            (phone, direction, body, timestamp, status, twilio_number)
        )
        conn.commit()
        print(f"[DB] Inserted message: {phone=} {direction=} {body[:50]!r} {timestamp=} {status=} {twilio_number=}")
    else:
        print(f"[DB] Skipped duplicate: {phone=} {direction=} {body[:50]!r}")

    conn.close()

    # Emit to frontend
    socketio.emit("new_message", {
        "phone": phone,
        "body": body,
        "direction": direction,
        "timestamp": timestamp
    })

    # ---------------------------
    # Tagging hook (added)
    # ---------------------------
    if direction == "inbound":
        # Remove drip assignment if contact replies
        remove_drip_assignment(phone)
        tag = get_tag_for_message(body)
        if tag:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE contacts SET tag=? WHERE phone=?", (tag, phone))
            conn.commit()
            conn.close()
            print(f"[Tagging] {phone} tagged as {tag} (msg: {body[:50]!r})")
# === DRIP SCHEDULER ===
def process_drip_assignments():
    now = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get all active assignments
    c.execute("SELECT id, contact_phone, drip_id, assigned_at FROM contact_drip_assignments WHERE completed=0")
    assignments = c.fetchall()
    for assign_id, phone, drip_id, assigned_at in assignments:
        # Get all drip messages for this drip
        c2 = conn.cursor()
        c2.execute("SELECT day_offset, message_template FROM drip_messages WHERE drip_id=? ORDER BY day_offset ASC", (drip_id,))
        drip_msgs = c2.fetchall()
        # Parse assigned_at
        assigned_dt = parser.parse(assigned_at)
        days_since = (now - assigned_dt).days
        # For each message, check if it should be sent
        for day_offset, msg_template in drip_msgs:
            # Only send if day_offset matches days_since and not already sent
            # Check if a message with this template has already been sent to this phone after assigned_at
            c2.execute("SELECT 1 FROM messages WHERE phone=? AND body=? AND timestamp>=?", (phone, msg_template, assigned_at))
            already_sent = c2.fetchone()
            if not already_sent and days_since >= int(day_offset):
                # Send at the same time of day as assigned_at
                send_time = assigned_dt + timedelta(days=int(day_offset))
                if now >= send_time and now < send_time + timedelta(minutes=10):  # 10 min window
                    # Use the most recent twilio_number for this thread, or fallback
                    c2.execute("SELECT twilio_number FROM messages WHERE phone=? AND twilio_number IS NOT NULL AND twilio_number != '' ORDER BY timestamp DESC LIMIT 1", (phone,))
                    row = c2.fetchone()
                    from_number = row[0] if row and row[0] else TWILIO_NUMBERS[0]
                    try:
                        client.messages.create(to=phone, from_=from_number, body=msg_template)
                        log_message(phone=phone, direction="outbound", body=msg_template, twilio_number=from_number)
                        print(f"[Drip] Sent drip message to {phone} for drip {drip_id} (day {day_offset})")
                    except Exception as e:
                        print(f"[Drip] Failed to send drip message to {phone}: {e}")
    conn.close()

def drip_scheduler_loop():
    while True:
        try:
            process_drip_assignments()
        except Exception as e:
            print(f"[Drip Scheduler] Error: {e}")
        time.sleep(600)  # Run every 10 minutes

# Start the scheduler in a background thread
drip_thread = threading.Thread(target=drip_scheduler_loop, daemon=True)
drip_thread.start()

# --- Provide contact columns for forms ---
def get_contact_columns():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(contacts)")
    columns = [row[1] for row in c.fetchall()]
    conn.close()
    return columns

def get_conversation(phone):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE phone=? ORDER BY timestamp ASC", (phone,))
    convo = c.fetchall()
    conn.close()
    return convo

def get_threads(search=None, tag_filters=None, box=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")

    if not box:
        box = 'all'

    c.execute("SELECT phone, MAX(timestamp) as latest_time FROM messages GROUP BY phone ORDER BY latest_time DESC")
    phones = c.fetchall()
    threads = []

    for contact_phone, latest_time in phones:
        # Get last 2 inbound messages for preview
        c.execute("""
            SELECT body, timestamp FROM messages
            WHERE phone=? AND direction='inbound'
            ORDER BY timestamp DESC LIMIT 2
        """, (contact_phone,))
        inbound_rows = c.fetchall()

        if inbound_rows:
            latest_body = "\n".join([(row[0] or "") for row in inbound_rows[::-1]])
            latest_timestamp = inbound_rows[0][1]  # timestamp of most recent inbound
            latest_direction = "inbound"
            twilio_number = ""  # not needed for preview
        else:
            # Fallback → latest message of any type
            c.execute("""
                SELECT body, direction, timestamp, twilio_number 
                FROM messages 
                WHERE phone=? ORDER BY timestamp DESC LIMIT 1
            """, (contact_phone,))
            latest_row = c.fetchone()
            latest_body = latest_row[0] if latest_row else ""
            latest_direction = latest_row[1] if latest_row else ""
            latest_timestamp = latest_row[2] if latest_row else latest_time
            twilio_number = latest_row[3] if latest_row else ""

        # Fetch contact info
        c.execute("SELECT Name, Address, tag, notes FROM contacts WHERE phone=?", (contact_phone,))
        contact_row = c.fetchone()
        name = contact_row[0] if contact_row else ""
        address = contact_row[1] if contact_row else ""
        tag = contact_row[2] if contact_row and len(contact_row) > 2 else ""
        notes = contact_row[3] if contact_row and len(contact_row) > 3 else ""

        # Filter by box type
        if box == 'inbox' and latest_direction != 'inbound':
            continue
        if box == 'sent' and not str(latest_direction).startswith('outbound'):
            continue

        # Filter by tag
        if tag_filters:
            tag_val = (tag or "").strip().lower()
            match = False
            for tf in tag_filters:
                if tf == "__no_tag__" and not tag_val:
                    match = True
                elif tag_val == tf:
                    match = True
            if not match:
                continue

        # Filter by search
        if search and search.strip() and search.lower() not in (str(contact_phone) + str(name) + str(address)).lower():
            continue

        # Format timestamp
        dt = parser.parse(str(latest_timestamp)) if latest_timestamp else datetime.now()
        ts_formatted = dt.strftime('%Y-%m-%d %I:%M:%S %p CST')

        # Build thread entry
        threads.append({
            "phone": contact_phone,
            "name": name,
            "address": address,
            "tag": tag,
            "notes": notes,
            "latest": latest_body,
            "latest_direction": latest_direction,  # add this line
            "timestamp": ts_formatted,
            "twilio_number": twilio_number,
            "unread": False
        })


    conn.close()
    return threads


def deduplicate_and_import(preview_only=False, lookback_days=3):
    """
    Import recent messages from Twilio into the local DB.
    Uses a sliding window to ensure no outbound-api messages are skipped.
    """
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz('America/Chicago')

    # Step 1: Prepare deduplication set from DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone, direction, body, timestamp FROM messages")
    db_msgs = set((row[0], row[1], row[2], str(row[3])) for row in c.fetchall())
    conn.close()

    # Step 2: Sliding window - fetch last N days
    since_dt = datetime.utcnow() - timedelta(days=lookback_days)
    fetch_kwargs = {"limit": 1000, "date_sent_after": since_dt.isoformat() + "Z"}

    twilio_msgs = []
    total_msgs = 0

    for msg in client.messages.list(**fetch_kwargs):
        direction = msg.direction  # Twilio gives 'inbound', 'outbound-api', 'outbound-reply'
        phone = msg.from_ if direction == "inbound" else msg.to
        twilio_number = msg.to if direction == "inbound" else msg.from_
        body = msg.body
        ts = parser.parse(msg.date_sent.isoformat()).astimezone(to_zone).strftime('%Y-%m-%d %H:%M:%S') if msg.date_sent else ""
        status = msg.status
        sid = msg.sid  # unique Twilio message ID

        # Dedup check: use sid if available, else fallback on (phone, direction, body, ts)
        key = (phone, direction, body, ts)
        if key not in db_msgs:
            twilio_msgs.append((phone, direction, body, ts, status, twilio_number))
        total_msgs += 1

    if preview_only:
        print(f"[Preview] Found {len(twilio_msgs)} new of {total_msgs} fetched.")
        return

    # Step 3: Insert new messages
    for phone, direction, body, timestamp, status, twilio_number in twilio_msgs:
        log_message(
            phone=phone,
            direction=direction,
            body=body,
            status=status,
            timestamp=timestamp,
            twilio_number=twilio_number
        )

    print(f"[Sync] Imported {len(twilio_msgs)} new messages from Twilio (checked {total_msgs}).")

def run_twilio_sync_background():
    def sync():
        print("[Startup] Syncing Twilio messages for last 3 days...")
        try:
            deduplicate_and_import(lookback_days=3)
        except Exception as e:
            print(f"[Twilio Sync Error] {e}")
    threading.Thread(target=sync, daemon=True).start()

# Start Twilio sync in background at startup
run_twilio_sync_background()

def update_webhooks(public_url):
    for number in TWILIO_NUMBERS:
        incoming = client.incoming_phone_numbers.list(phone_number=number)
        if incoming: incoming[0].update(sms_url=f"{public_url}/sms-webhook", sms_method="POST")
        
def get_tag_for_message(body: str):
    body = body.lower().strip()
    if "stop" in body:
        return "DNC"       # Stop always wins
    elif "wrong" in body:
        return "Wrong number"
    return None

def process_message(phone, direction, body, timestamp):
    if direction != "inbound":
        return

    tag = get_tag_for_message(body)
    if tag:
        print(f"Tagging {phone} with {tag} (msg: {body})")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # assumes your contacts table has phone + tag fields
        c.execute("UPDATE contacts SET tag=? WHERE phone=?", (tag, phone))
        conn.commit()
        conn.close()


# Helper: get all weeks (Mon-Sun) with data in messages table
def get_available_weeks():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MIN(date(timestamp)), MAX(date(timestamp)) FROM messages")
    min_date, max_date = c.fetchone()
    if not min_date or not max_date:
        return []
    from datetime import datetime, timedelta
    min_dt = datetime.strptime(min_date, "%Y-%m-%d")
    max_dt = datetime.strptime(max_date, "%Y-%m-%d")
    # Find first Monday on/after min_dt
    start = min_dt - timedelta(days=(min_dt.weekday()))
    weeks = []
    cur = start
    while cur <= max_dt:
        end = cur + timedelta(days=6)
        label = f"{cur.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        weeks.append(label)
        cur += timedelta(days=7)
    # Always include current week (Monday-Sunday)
    from datetime import date
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    current_sunday = current_monday + timedelta(days=6)
    current_label = f"{current_monday.strftime('%Y-%m-%d')} to {current_sunday.strftime('%Y-%m-%d')}"
    if current_label not in weeks:
        weeks.append(current_label)
    conn.close()
    return weeks

# Helper: load KPI rows for a given week (label: YYYY-MM-DD to YYYY-MM-DD)
def load_kpi_rows_for_week(week_label):
    if not os.path.exists(DB_PATH) or not week_label:
        return [], [], [], [], [], {"total_sent": 0, "total_delivered": 0, "total_replies": 0, "avg_reply_time": "N/A"}
    start_str, end_str = week_label.split(' to ')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from datetime import datetime, timedelta
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    num_days = (end - start).days + 1
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]
    sent, delivered, replies = [], [], []
    for d in dates:
        c.execute("SELECT COUNT(*) FROM messages WHERE direction LIKE 'outbound%' AND date(timestamp)=?", (d,))
        sent.append(c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM messages WHERE direction LIKE 'outbound%' AND status='delivered' AND date(timestamp)=?", (d,))
        delivered.append(c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM messages WHERE direction='inbound' AND date(timestamp)=?", (d,))
        replies.append(c.fetchone()[0])
    delivery_rate = [round((d/s)*100,2) if s else 0 for s,d in zip(sent, delivered)]
    # Weekly totals
    total_sent = sum(sent)
    total_delivered = sum(delivered)
    total_replies = sum(replies)
    avg_delivery_rate = round((total_delivered/total_sent)*100,2) if total_sent else 0
    response_rate = round((total_replies/total_sent)*100,2) if total_sent else 0
    latest = {
        "total_sent": total_sent,
        "total_delivered": total_delivered,
        "total_replies": total_replies,
        "avg_delivery_rate": avg_delivery_rate,
        "response_rate": response_rate,
        "avg_reply_time": "N/A"
    }
    conn.close()
    return dates, sent, delivered, delivery_rate, replies, latest

# Helper: get all months with data in messages table
def get_available_months():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT strftime('%Y-%m', timestamp) as ym FROM messages ORDER BY ym")
    months = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    return months

# Helper: load KPI rows for a given month (YYYY-MM)
def load_kpi_rows_for_month(month):
    if not os.path.exists(DB_PATH) or not month:
        return [], [], [], [], [], {"total_sent": 0, "total_delivered": 0, "total_replies": 0, "avg_reply_time": "N/A"}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get all days in the month
    c.execute("SELECT MIN(date(timestamp)), MAX(date(timestamp)) FROM messages WHERE strftime('%Y-%m', timestamp)=?", (month,))
    min_date, max_date = c.fetchone()
    if not max_date:
        return [], [], [], [], [], {"total_sent": 0, "total_delivered": 0, "total_replies": 0, "avg_reply_time": "N/A"}
    from datetime import datetime, timedelta
    start = datetime.strptime(min_date, "%Y-%m-%d")
    end = datetime.strptime(max_date, "%Y-%m-%d")
    num_days = (end - start).days + 1
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]
    sent, delivered, replies = [], [], []
    for d in dates:
        c.execute("SELECT COUNT(*) FROM messages WHERE direction LIKE 'outbound%' AND date(timestamp)=?", (d,))
        sent.append(c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM messages WHERE direction LIKE 'outbound%' AND status='delivered' AND date(timestamp)=?", (d,))
        delivered.append(c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM messages WHERE direction='inbound' AND date(timestamp)=?", (d,))
        replies.append(c.fetchone()[0])
    delivery_rate = [round((d/s)*100,2) if s else 0 for s,d in zip(sent, delivered)]
    latest = {"total_sent": sent[-1] if sent else 0,
              "total_delivered": delivered[-1] if delivered else 0,
              "total_replies": replies[-1] if replies else 0,
              "avg_reply_time": "N/A"}
    conn.close()
    return dates, sent, delivered, delivery_rate, replies, latest

# === KPI Dashboard logic ===
def get_lead_breakdown(start_date=None, end_date=None):
    """
    Returns a dict of tag -> count from contacts table, plus total.
    If start_date and end_date are provided, filters replies by date.
    """
    if not os.path.exists(DB_PATH):
        return {"Hot": 0, "Nurture": 0, "Drip": 0, "Not interested": 0, "Wrong Number": 0, "DNC": 0, "total": 0}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = """
        SELECT contacts.tag, COUNT(messages.id)
        FROM messages
        JOIN contacts ON messages.phone = contacts.phone
        WHERE messages.direction = 'inbound'
    """
    params = []
    if start_date and end_date:
        query += " AND date(messages.timestamp) >= ? AND date(messages.timestamp) <= ?"
        params.extend([start_date, end_date])
    query += " GROUP BY contacts.tag"
    c.execute(query, params)
    rows = c.fetchall()
    tags = ["Hot", "Nurture", "Drip", "Not interested", "Wrong Number", "DNC"]
    result = {tag: 0 for tag in tags}
    for tag, count in rows:
        if tag in result:
            result[tag] = count
    result["total"] = sum(result.values())
    conn.close()
    return result

def load_kpi_rows(limit_days=60):
    """
    Loads rows from messages table in messages.db.
    Returns arrays: dates (YYYY-MM-DD), sent, delivered, delivery_rate, replies, latest_row_dict
    """
    if not os.path.exists(DB_PATH):
        return [], [], [], [], [], {"total_sent": 0, "total_delivered": 0, "total_replies": 0, "avg_reply_time": "N/A"}

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get all message dates in the last N days
    c.execute("SELECT MIN(date(timestamp)), MAX(date(timestamp)) FROM messages")
    min_date, max_date = c.fetchone()
    if not max_date:
        return [], [], [], [], [], {"total_sent": 0, "total_delivered": 0, "total_replies": 0, "avg_reply_time": "N/A"}

    # Build list of last limit_days dates
    from datetime import datetime, timedelta
    end_date = datetime.strptime(max_date, "%Y-%m-%d")
    dates = [(end_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(limit_days))]

    sent, delivered, replies = [], [], []
    for d in dates:
        # Sent: outbound messages
        c.execute("SELECT COUNT(*) FROM messages WHERE direction LIKE 'outbound%' AND date(timestamp)=?", (d,))
        sent.append(c.fetchone()[0])
        # Delivered: outbound messages with status delivered
        c.execute("SELECT COUNT(*) FROM messages WHERE direction LIKE 'outbound%' AND status='delivered' AND date(timestamp)=?", (d,))
        delivered.append(c.fetchone()[0])
        # Replies: inbound messages
        c.execute("SELECT COUNT(*) FROM messages WHERE direction='inbound' AND date(timestamp)=?", (d,))
        replies.append(c.fetchone()[0])

    delivery_rate = [round((d/s)*100,2) if s else 0 for s,d in zip(sent, delivered)]

    # Latest day stats
    latest = {"total_sent": 0, "total_delivered": 0, "total_replies": 0, "avg_reply_time": "N/A"}
    if dates:
        latest = {
            "total_sent": sent[-1] if sent else 0,
            "total_delivered": delivered[-1] if delivered else 0,
            "total_replies": replies[-1] if replies else 0,
            "avg_reply_time": "N/A"  # Not calculated here
        }

    conn.close()
    return dates, sent, delivered, delivery_rate, replies, latest

    # ...existing code for dashboard route remains...
    # Remove this duplicate dashboard() definition
# --- Helper: get top campaigns for dashboard ---
def get_top_campaigns(limit=3):
    """
    Returns a list of dicts: [{name, Hot, Nurture, Drip, Not interested, Wrong Number, DNC, total}], sorted by total leads desc.
    """
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get replies by campaign and tag
    try:
        c.execute("""
            SELECT contacts.campaign, contacts.tag, COUNT(messages.id)
            FROM messages
            JOIN contacts ON messages.phone = contacts.phone
            WHERE messages.direction = 'inbound'
            GROUP BY contacts.campaign, contacts.tag
        """)
    except Exception:
        try:
            c.execute("""
                SELECT contacts.Campaign, contacts.tag, COUNT(messages.id)
                FROM messages
                JOIN contacts ON messages.phone = contacts.phone
                WHERE messages.direction = 'inbound'
                GROUP BY contacts.Campaign, contacts.tag
            """)
        except Exception:
            return []
    rows = c.fetchall()
    from collections import defaultdict
    tags = ["Hot", "Nurture", "Drip", "Not interested", "Wrong Number", "DNC"]
    camp_data = defaultdict(lambda: {tag: 0 for tag in tags})
    for camp, tag, count in rows:
        camp = camp or "(No Campaign)"
        if tag in camp_data[camp]:
            camp_data[camp][tag] += count
    result = []
    for camp, tag_counts in camp_data.items():
        entry = {"name": camp}
        entry.update(tag_counts)
        entry["total"] = sum(tag_counts.values())
        result.append(entry)
    result.sort(key=lambda x: (-x["total"], x["name"]))
    conn.close()
    return result[:limit]
    
# --- Context processor to inject TWILIO_NUMBERS into all templates ---
@app.context_processor
def inject_twilio_numbers():
    return {"TWILIO_NUMBERS": TWILIO_NUMBERS}

# --- MIGRATION: Ensure contact_drip_assignments table exists ---
def ensure_drip_assignment_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS contact_drip_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_phone TEXT,
            drip_id INTEGER,
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

ensure_drip_assignment_table()


# ── ROUTES ────────────────────────────────────────────────────────

@app.route("/")
@app.route("/dashboard", methods=["GET"])
def dashboard():
    # Get week from query param, default to latest week in DB
    week = request.args.get("week")
    weeks = get_available_weeks()
    if not week and weeks:
        week = weeks[-1]  # latest week
    dates, sent, delivered, delivery_rate, replies, latest = load_kpi_rows_for_week(week)
    # Parse week range for filtering
    if week:
        start_str, end_str = week.split(' to ')
        lead_breakdown = get_lead_breakdown(start_str, end_str)
    else:
        lead_breakdown = get_lead_breakdown()
    top_campaigns = get_top_campaigns()
    return render_template("kpi_dashboard.html",
                          dates=dates,
                          sent=sent,
                          delivered=delivered,
                          delivery_rate=delivery_rate,
                          replies=replies,
                          latest=latest,
                          lead_breakdown=lead_breakdown,
                          top_campaigns=top_campaigns,
                          weeks=weeks,
                          selected_week=week)

@app.route("/inbox")
def inbox():
    search = request.args.get("search", "")
    box = request.args.get("box", "inbox")
    tags_filter = request.args.getlist("tags")
    selected_phone = request.args.get("selected")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    all_threads = get_threads(search=search, box=box)
    # Filter out threads with default tag 🏷️ in inbox
    if box == 'inbox':
        all_threads = [t for t in all_threads if t.get("tag") != "🏷️"]
    if box == 'unread':
        all_threads = [
            t for t in all_threads
            if not t.get("tag") and t.get("latest") and t.get("latest").strip() and "inbound" in t.get("latest_direction", "inbound")
        ]
    if tags_filter:
        if "__ALL__" not in tags_filter:
            if "__NO_tag__" in tags_filter:
                all_threads = [t for t in all_threads if not t.get("tag")]
            else:
                all_threads = [t for t in all_threads if t.get("tag") in tags_filter]
        else:
            excluded = {"DNC", "No tag", "Wrong Number", "Unverified", "Not interested"}
            all_threads = [t for t in all_threads if t.get("tag") not in excluded]
    def parse_date(ts):
        try:
            return datetime.strptime(str(ts)[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    if from_date:
        from_d = datetime.strptime(from_date, "%Y-%m-%d").date()
        all_threads = [
            t for t in all_threads
            if parse_date(t.get("timestamp")) and parse_date(t["timestamp"]) >= from_d
        ]
    if to_date:
        to_d = datetime.strptime(to_date, "%Y-%m-%d").date()
        all_threads = [
            t for t in all_threads
            if parse_date(t.get("timestamp")) and parse_date(t["timestamp"]) <= to_d
        ]
    threads = all_threads  
    unread_count = len([t for t in all_threads if t.get("latest_direction") == "inbound" and not t.get("read")])
    unanswered_count = len([t for t in all_threads if t.get("latest_direction") == "inbound" and not t.get("responded")])
    reminders_count = 0  # later query reminders table
    no_tags_count = len([t for t in all_threads if not t.get("tag")])
    return render_template(
        "dashboard.html",
        threads=threads,
        search=search,
        box=box,
        selected_phone=selected_phone,
        total_threads=len(all_threads),
        tags=TAGS,
        tag_icons=TAG_ICONS,
        TWILIO_NUMBERS=TWILIO_NUMBERS,
        unread_count=unread_count,
        unanswered_count=unanswered_count,
        reminders_count=reminders_count,
        no_tags_count=no_tags_count
    )


# --- Update contact endpoint ---
@app.route("/update-contact", methods=["POST"])
def update_contact():
    data = request.get_json(force=True)
    phone = data.get("phone")
    updates = {k: v for k, v in data.items() if k != "phone"}
    if not phone or not updates:
        return jsonify(success=False, error="Missing phone or update fields"), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values()) + [phone]
    c.execute(f"UPDATE contacts SET {set_clause} WHERE phone=?", values)
    conn.commit()
    conn.close()
    return jsonify(success=True)

# --- Add contact endpoint ---
@app.route("/add-contact", methods=["POST"])
def add_contact():
    data = request.get_json(force=True)
    columns = get_contact_columns()
    values = [data.get(col, "") for col in columns]
    if not data.get("phone"):
        return jsonify(success=False, error="Phone is required"), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ", ".join(["?" for _ in columns])
    c.execute(f"INSERT INTO contacts ({', '.join(columns)}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()
    return jsonify(success=True)
# === Drip Automations ===
@app.route("/assign-drip", methods=["POST"])
def assign_drip():
    data = request.get_json(force=True)
    phone = data.get("phone")
    drip_id = data.get("drip_id")
    if not phone or not drip_id:
        return jsonify({"success": False, "error": "Missing phone or drip_id"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get drip name
    c.execute("SELECT name FROM drip_automations WHERE id=?", (drip_id,))
    drip_row = c.fetchone()
    drip_name = drip_row[0] if drip_row else ""
    # Remove any previous assignment for this contact (optional, only one drip at a time)
    c.execute("DELETE FROM contact_drip_assignments WHERE contact_phone=?", (phone,))
    c.execute("INSERT INTO contact_drip_assignments (contact_phone, drip_id) VALUES (?, ?)", (phone, drip_id))
    # Set tag as 'Drip - [Drip Name]'
    if drip_name:
        tag_val = f"Drip - {drip_name}"
        c.execute("UPDATE contacts SET tag=? WHERE phone=?", (tag_val, phone))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# === Drip Messages Popup ===
@app.route("/drip-messages/<int:drip_id>")
def drip_messages_popup(drip_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM drip_automations WHERE id=?", (drip_id,))
    drip_row = c.fetchone()
    drip_name = drip_row[0] if drip_row else ""
    c.execute("SELECT day_offset, message_template FROM drip_messages WHERE drip_id=? ORDER BY day_offset ASC", (drip_id,))
    messages = [
        {"day_offset": row[0], "message_template": row[1]} for row in c.fetchall()
    ]
    conn.close()
    return render_template("drip_messages_popup.html", drip={"name": drip_name}, messages=messages)

@app.route("/reminders/new", methods=["POST"])
def new_reminder():
    thread_phone = request.form.get("thread_phone")
    remind_at = request.form.get("remind_at")
    note = request.form.get("note")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO reminders (thread_phone, remind_at, note)
        VALUES (?, ?, ?)
    """, (thread_phone, remind_at, note))
    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/thread/<phone>")
def thread_view(phone):
    # === Get messages ===
    convo = get_conversation(phone)
    convo_out = []
    for row in convo:
        is_outbound = str(row[2]).startswith("outbound")
        convo_out.append({
            "row": row,
            "body": row[3],
            "timestamp": row[4],
            "twilio_number": row[5],
            "is_outbound": is_outbound
        })

    # === Get contact ===
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(contacts)")
    col_names = [desc[1] for desc in c.fetchall()]

    c.execute("SELECT * FROM contacts WHERE phone=?", (phone,))
    row = c.fetchone()
    contact = {col: str(val) if val is not None else "" for col, val in zip(col_names, row)} if row else {}

    # === Normalize name ===
    csv_name = contact.get("Name", "").strip()
    db_name = contact.get("db_name", "").strip() if "db_name" in contact else ""
    fallback_name = contact.get("name", "").strip() if "name" in contact else ""

    # Choose best available
    name = csv_name or db_name or fallback_name
    if not name and "name" in contact:  # catch-all for lowercase
        name = contact["name"].strip()

    # === Pick main fields ===
    main_fields = [
        "Name", "Address", "County", "Mailing Address", "Phone", "notes",
        "Last Sale Amount", "Last Sale Recording Date", "Effective Year Built",
        "Bd/Ba", "Owner 2", "Building Sqft", "Alt Phone 1", "Alt Phone 2"
    ]
    contact_main = {k: contact.get(k, "") for k in main_fields} if contact else {}

    # === Build response ===
    return jsonify(dict(
        messages=convo_out,
        contact=contact_main,
        contact_all=contact,
        contact_headers=col_names,
        csv_name=csv_name,
        db_name=db_name,
        name=name,              # 🔑 Always return a top-level "name"
        tag=contact.get("tag", ""),
        notes=contact.get("notes", "")
    ))


@app.route("/send", methods=["POST"])
def send_sms():
    data = request.json
    to, body = data["to"], data["body"]

    # Pick the most recent Twilio number for this thread
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT twilio_number FROM messages
        WHERE phone=? AND twilio_number IS NOT NULL AND twilio_number != ''
        ORDER BY timestamp DESC LIMIT 1
    """, (to,))
    row = c.fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify(success=False, error="No previous Twilio number found for this thread.")

    from_number = row[0]

    try:
        # Send via Twilio
        message = client.messages.create(to=to, from_=from_number, body=body)

        # Poll a few times for a status update (optional)
        status = None
        for _ in range(5):
            msg = client.messages(message.sid).fetch()
            if msg.status not in ("queued", "sending", "accepted"):
                break
            time.sleep(1)
        status = msg.status

        # Log it explicitly with from_number
        log_message(
            phone=to,
            direction="outbound",
            body=body,
            status=status,
            twilio_number=from_number
        )

        return jsonify(success=True, status=status)
    except Exception as e:
        return jsonify(success=False, error=str(e))


@app.route("/call", methods=["POST"])
def call_contact():
    # This endpoint is deprecated. All calling should use Twilio Client JS (WebRTC) in the browser.
    return jsonify(success=False, error="Call bridging is disabled. Use browser calling via Twilio Client JS/WebRTC."), 400

@app.route("/create_thread", methods=["POST"])
def create_thread():
    data = request.get_json(force=True)
    to = data.get("to")
    from_number = data.get("from")
    body = data.get("body")

    if not to or not body:
        return jsonify({"success": False, "error": "Missing to/body"}), 400

    try:
        # Send SMS via Twilio
        message = client.messages.create(to=to, from_=from_number, body=body)

        # Log in messages table so the new thread shows up
        log_message(phone=to, direction="outbound", body=body, twilio_number=from_number)

        # Ensure a contact row exists for this number
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM contacts WHERE phone=?", (to,))
        if not c.fetchone():
            c.execute("INSERT INTO contacts (phone, tag, notes) VALUES (?, ?, ?)", (to, "No tag", ""))
            conn.commit()
        conn.close()

        return jsonify({"success": True, "thread_id": to})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/update-meta", methods=["POST"])
def update_meta():
    data = request.get_json(force=True)
    phone, tag, notes = data.get("phone"), data.get("tag", ""), data.get("notes", "")

    # Default to "No tag" if empty
    if not tag:
        tag = "No tag"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if contact exists
    c.execute("SELECT 1 FROM contacts WHERE phone=?", (phone,))
    if c.fetchone():
        c.execute("UPDATE contacts SET tag=?, notes=? WHERE phone=?", (tag, notes, phone))
    else:
        # Insert new row with default "No tag"
        c.execute("INSERT INTO contacts (phone, tag, notes) VALUES (?, ?, ?)", (phone, tag, notes))

    conn.commit()
    conn.close()

    socketio.emit("meta_updated", {"phone": phone, "tag": tag, "notes": notes})
    return jsonify({"success": True})


@app.route("/sms-webhook", methods=["POST"])
def sms_webhook():
    data = request.form.to_dict()
    phone, body = data.get('From'), data.get('Body')
    timestamp = datetime.utcnow().isoformat()
    log_message(phone, 'inbound', body, timestamp=timestamp)
    return 'OK', 200

@app.route("/twiml", methods=['GET','POST'])
def serve_twiml():
    lead_number = request.args.get('lead')
    if not lead_number: return "Missing 'lead' number", 400
    vr = VoiceResponse()
    vr.dial(lead_number)
    return Response(str(vr), mimetype='text/xml')

# === Drip Automations ===
@app.route("/drip-automations")
def drip_automations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT d.id, d.name, m.day_offset, m.message_template
        FROM drip_automations d
        LEFT JOIN drip_messages m ON d.id = m.drip_id
        ORDER BY d.id ASC, m.day_offset ASC
    """)
    automations = [
        {"id": row[0], "name": row[1], "day_offset": row[2], "message_template": row[3]}
        for row in c.fetchall()
    ]
    # Get contacts table columns for merge field dropdown
    c.execute("PRAGMA table_info(contacts)")
    contact_columns = [row[1] for row in c.fetchall()]
    conn.close()
    # If AJAX (popup), render only the popup partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('popup') == '1':
        return render_template("drip_select_popup.html", automations=automations)
    return render_template("drip_automations.html", automations=automations, contact_columns=contact_columns)


@app.route("/drip-automations/new", methods=["GET", "POST"])
def new_drip_automation():
    if request.method == "POST":
        name = request.form.get("name")
        messages = request.form.getlist("messages[]")  # multiple textarea values
        days = request.form.getlist("days[]")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Insert parent drip
        c.execute("INSERT INTO drip_automations (name) VALUES (?)", (name,))
        drip_id = c.lastrowid

        # Insert messages
        for day, msg in zip(days, messages):
            c.execute("""
                INSERT INTO drip_messages (drip_id, day_offset, message_template)
                VALUES (?, ?, ?)
            """, (drip_id, day, msg))

        conn.commit()
        conn.close()
        return redirect("/drip-automations")
    else:
        # GET: render new drip form with contact columns
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("PRAGMA table_info(contacts)")
        contact_columns = [row[1] for row in c.fetchall()]
        conn.close()
        return render_template("new_drip.html", contact_columns=contact_columns)



@app.route("/drip-automations/edit/<int:drip_id>", methods=["GET", "POST"])
def edit_drip_automation(drip_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name")
        messages = request.form.getlist("messages[]")
        days = request.form.getlist("days[]")

        # update name
        c.execute("UPDATE drip_automations SET name=? WHERE id=?", (name, drip_id))

        # delete old messages and reinsert
        c.execute("DELETE FROM drip_messages WHERE drip_id=?", (drip_id,))
        for day, msg in zip(days, messages):
            c.execute("""
                INSERT INTO drip_messages (drip_id, day_offset, message_template)
                VALUES (?, ?, ?)
            """, (drip_id, day, msg))

        conn.commit()
        conn.close()
        return redirect("/drip-automations")
    else:
        # fetch automation + messages
        c.execute("SELECT id, name FROM drip_automations WHERE id=?", (drip_id,))
        drip = c.fetchone()
        c.execute("SELECT id, day_offset, message_template FROM drip_messages WHERE drip_id=? ORDER BY day_offset ASC", (drip_id,))
        messages = [{"id": row[0], "day_offset": row[1], "message_template": row[2]} for row in c.fetchall()]
        # fetch contact columns
        c.execute("PRAGMA table_info(contacts)")
        contact_columns = [row[1] for row in c.fetchall()]
        conn.close()
        if not drip:
            return "Drip automation not found", 404
        return render_template("edit_drip.html", drip={"id": drip[0], "name": drip[1]}, messages=messages, contact_columns=contact_columns)


@app.route("/drip-automations/delete/<int:drip_id>", methods=["POST"])
def delete_drip_automation(drip_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM drip_automations WHERE id=?", (drip_id,))
    conn.commit()
    conn.close()
    return redirect("/drip-automations")


@app.route("/export-contacts", methods=["POST"])
def export_contacts():
    data = request.get_json(force=True)
    phones = data.get("phones")
    if not phones: return jsonify({"error":"No phones provided"}),400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(contacts)")
    col_names = [row[1] for row in c.fetchall()]
    rows=[]
    for phone in phones:
        c.execute(f"SELECT {', '.join(col_names)} FROM contacts WHERE phone=?", (phone,))
        contact_row = c.fetchone()
        if contact_row: rows.append(contact_row)
    conn.close()
    def generate():
        with open('/tmp/selected_contacts.csv','w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f)
            writer.writerow(col_names)
            for row in rows: writer.writerow(row)
        with open('/tmp/selected_contacts.csv','r',encoding='utf-8') as f: yield f.read()
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=selected_contacts.csv"})

@app.route("/add-to-leads", methods=["POST"])
def add_to_leads():
    data = request.get_json(force=True)
    phone = data.get("phone")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, address, tag, notes FROM contacts WHERE phone=?", (phone,))
    contact_row = c.fetchone()
    name = contact_row[0] if contact_row else ""
    address = contact_row[1] if contact_row else ""
    tag = contact_row[2] if contact_row and len(contact_row) > 2 else ""
    notes = contact_row[3] if contact_row and len(contact_row) > 3 else ""
    c.execute("SELECT body, twilio_number FROM messages WHERE phone=? ORDER BY timestamp DESC LIMIT 1", (phone,))
    msg_row = c.fetchone()
    body = msg_row[0] if msg_row else ""
    twilio_number = msg_row[1] if msg_row else ""
    conn.close()
    fields = ["phone","name","address","body","tag","notes","twilio_number"]
    row_data = [phone,name,address,body,tag,notes,twilio_number]
    file_exists = os.path.isfile(LEADS_CSV_PATH)
    with open(LEADS_CSV_PATH,"a",newline='',encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists: writer.writerow(fields)
        writer.writerow(row_data)
    return jsonify({"success": True})

# --- SEARCH Feature --- Database connection helper ---
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row  # Access columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# --- Fetch threads with optional contact info ---
def get_all_threads():
    conn = get_db()
    cursor = conn.cursor()
    # Left join contacts table to get name/address if available
    cursor.execute("""
        SELECT 
            m.phone, m.body, m.timestamp,
            c.name AS contact_name, 
            c.address AS contact_address
        FROM messages m
        LEFT JOIN contacts c ON m.phone = c.phone
        ORDER BY m.timestamp DESC
    """)
    rows = cursor.fetchall()
    return [
        {
            "phone": r["phone"],
            "body": r["body"],
            "timestamp": r["timestamp"],
            "contact_name": r["contact_name"],      # can be None
            "contact_address": r["contact_address"] # can be None
        }
        for r in rows
    ]

# --- Search endpoint ---
@app.route("/search_threads")
def search_threads():
    query = request.args.get("q", "").lower()

    all_threads = get_all_threads()

    if query:
        filtered = [
            t for t in all_threads
            if query in (t["phone"] or "").lower()
               or query in (t["body"] or "").lower()
        ]
    else:
        filtered = all_threads

    # No pagination → return all
    return jsonify({
        "threads": filtered,
        "page": 1,
        "total_pages": 1
    })



# ── SUPPORT /threads REDIRECT TO INDEX ───────────────────────────────
@app.route("/threads")
def threads_redirect():
    search = request.args.get("search", "")
    box = request.args.get("box", "inbox")
    tag = request.args.get("tags", "").strip()
    selected_phone = request.args.get("selected")

    from_date = request.args.get("from")
    to_date = request.args.get("to")

    # fetch all threads
    all_threads = get_threads(search=search, box=box)

    if box == 'unread':
        all_threads = [
            t for t in all_threads
            if not t.get("tag") and t.get("latest_direction") == "inbound"
        ]

    elif box == "reminders":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT thread_phone FROM reminders")
        phones_with_reminders = {row[0] for row in c.fetchall()}
        conn.close()
        all_threads = [t for t in all_threads if t.get("phone") in phones_with_reminders]

    elif box == "no-tags":
        all_threads = [t for t in all_threads if not t.get("tag")]

    # --- Tag filtering ---
    if tag:
        if tag == "__NO_tag__":
            all_threads = [t for t in all_threads if not t.get("tag")]
        elif tag != "__ALL__":  # specific tag filter
            all_threads = [t for t in all_threads if t.get("tag") == tag]

    # --- Date filtering ---
    def parse_date(ts):
        try:
            return datetime.strptime(str(ts)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    if from_date:
        from_d = datetime.strptime(from_date, "%Y-%m-%d").date()
        all_threads = [
            t for t in all_threads
            if parse_date(t.get("timestamp")) and parse_date(t["timestamp"]) >= from_d
        ]

    if to_date:
        to_d = datetime.strptime(to_date, "%Y-%m-%d").date()
        all_threads = [
            t for t in all_threads
            if parse_date(t.get("timestamp")) and parse_date(t["timestamp"]) <= to_d
        ]

    # no slicing → return all
    threads = all_threads  

    # Render only the thread list (AJAX expects this)
    return render_template("_threads_list.html", threads=threads, selected_phone=selected_phone)

@app.route("/batch-logs")
def batch_logs():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    rows = []
    if os.path.exists(BATCH_CSV):
        with open(BATCH_CSV, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_rows = list(reader)
            total = len(all_rows)
            start = (page - 1) * per_page
            end = start + per_page
            # newest first
            rows = list(reversed(all_rows))[start:end]
    else:
        total = 0

    return jsonify({
        "rows": rows,
        "page": page,
        "per_page": per_page,
        "total": total
    })


@app.route("/batch-sender", methods=["GET", "POST"])
def batch_sender():
    global batch_status, stop_batch
    if request.method == "POST":
        max_texts = int(request.form.get("max_texts", 200))
        min_interval = float(request.form.get("min_interval", 5.01))
        max_interval = float(request.form.get("max_interval", 9.99))

        # reset batch status and stop flag
        batch_status = {"sent": 0, "total": 0, "running": True}
        stop_batch = False

        def progress_cb(sent, total):
            batch_status["sent"] = sent
            batch_status["total"] = total
            # Only print every 100 messages or on completion
            if sent % 100 == 0 or sent == total:
                print(f"[Batch] Sent {sent}/{total}")

        def worker():
            from sms_sender_core import send_sms_batch
            send_sms_batch(
                max_texts,
                min_interval,
                max_interval,
                progress_cb,
                stop_flag=lambda: stop_batch
            )
            batch_status["running"] = False

        threading.Thread(target=worker, daemon=True).start()
        return redirect("/batch-sender")

    return render_template("batch_sender.html", status=batch_status)


@app.route("/batch-progress")
def batch_progress():
    return jsonify(batch_status)

@app.route("/stop-batch", methods=["POST"])
def stop_batch_route():
    global stop_batch
    stop_batch = True
    return jsonify({"stopped": True})

# ── SERVER LAUNCH ─────────────────────────────────────────────────
def run_flask(): socketio.run(app, port=PORT, debug=False)

def launch_dashboard():
    print("[Progress] Deduplicating and importing messages...")
    deduplicate_and_import()
    print("[Progress] Updating Twilio webhooks...")
    update_webhooks("https://resimpli-launch.onrender.com")
    print("[Progress] Launching dashboard in browser...")
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

if __name__ == "__main__":
    launch_dashboard()
