"""
One-time migration script: Move legacy contacts table data to normalized schema.
Assumes SQLAlchemy models for ContactsNew, Phones, ContactNotes, etc. are defined in sms_sender_core.py or similar.
"""

import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sms_sender_core import ContactsNew, Phones, ContactNotes  # Add other models as needed

# Legacy SQLite DB path
LEGACY_DB = 'contacts.db'  # Change if needed
# New DB connection string (PostgreSQL example)
NEW_DB = 'postgresql://user:password@localhost:5432/messages'  # Update credentials

# Connect to legacy SQLite
legacy_conn = sqlite3.connect(LEGACY_DB)
legacy_cur = legacy_conn.cursor()

# Connect to new DB
engine = create_engine(NEW_DB)
Session = sessionmaker(bind=engine)
session = Session()

# Fetch all legacy contacts
legacy_cur.execute('SELECT * FROM contacts')
rows = legacy_cur.fetchall()
columns = [desc[0] for desc in legacy_cur.description]

for row in rows:
    data = dict(zip(columns, row))
    # Example mapping: adjust as needed
    contact = ContactsNew(
        name=data.get('name'),
        address=data.get('address'),
        mailing_address=data.get('mailing_address'),
        campaign=data.get('campaign'),
        tag=data.get('tag'),
        notes=data.get('notes'),
    )
    session.add(contact)
    session.flush()  # Get contact.id
    # Phones
    phone = Phones(
        contact_id=contact.id,
        phone=data.get('phone'),
        is_primary=True
    )
    session.add(phone)
    # Notes (if any)
    if data.get('notes'):
        note = ContactNotes(
            contact_id=contact.id,
            note=data['notes']
        )
        session.add(note)
    # Add other mappings as needed

session.commit()
legacy_conn.close()
print('Migration complete.')
