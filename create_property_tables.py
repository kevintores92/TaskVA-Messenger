import sqlite3
DB_PATH = "messages.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Properties table
c.execute("""
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    unit TEXT,
    city TEXT,
    state TEXT,
    zip TEXT
)
""")

# Contacts table
c.execute("""
CREATE TABLE IF NOT EXISTS contacts_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    type TEXT
)
""")

# Phones table
c.execute("""
CREATE TABLE IF NOT EXISTS phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE
)
""")

# Property-Contact relationship
c.execute("""
CREATE TABLE IF NOT EXISTS property_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    contact_id INTEGER,
    role TEXT,
    FOREIGN KEY(property_id) REFERENCES properties(id),
    FOREIGN KEY(contact_id) REFERENCES contacts_new(id)
)
""")

# Contact-Phone relationship
c.execute("""
CREATE TABLE IF NOT EXISTS contact_phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    phone_id INTEGER,
    FOREIGN KEY(contact_id) REFERENCES contacts_new(id),
    FOREIGN KEY(phone_id) REFERENCES phones(id)
)
""")

# Property Activity Log
c.execute("""
CREATE TABLE IF NOT EXISTS property_activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    activity_type TEXT,
    details TEXT,
    user TEXT,
    FOREIGN KEY(property_id) REFERENCES properties(id)
)
""")

conn.commit()
conn.close()
print("Property, contacts, phones, relationships, and activity log tables created.")
