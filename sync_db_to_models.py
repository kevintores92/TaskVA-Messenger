"""
Sync messages.db schema to match models.py.
- Adds missing columns to existing tables
- Creates missing tables
- Does not drop or delete any data
- Prepares for migration/distribution
"""
import sqlite3

DB_PATH = 'messages.db'

# --- Table definitions from models.py ---
tables = {
    'contacts_new': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('first_name', 'TEXT'),
        ('last_name', 'TEXT'),
        ('phone', 'TEXT'),
        ('address', 'TEXT'),
        ('mailing_care_of_name', 'TEXT'),
        ('mailing_street_address', 'TEXT'),
        ('mailing_unit', 'TEXT'),
        ('mailing_city', 'TEXT'),
        ('mailing_state', 'TEXT'),
        ('mailing_zip', 'TEXT'),
        ('mailing_county', 'TEXT'),
        ('type', 'TEXT'),
        ('tag', 'TEXT'),
        ('notes', 'TEXT'),
    ],
    'phones': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('phone', 'TEXT UNIQUE NOT NULL'),
    ],
    'contact_phones': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('contact_id', 'INTEGER'),
        ('phone_id', 'INTEGER'),
    ],
    'properties': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('street_address', 'TEXT'),
        ('unit', 'TEXT'),
        ('city', 'TEXT'),
        ('state', 'TEXT'),
        ('zip', 'TEXT'),
        ('county', 'TEXT'),
        ('zillow_link', 'TEXT'),
        ('bd_ba', 'TEXT'),
        ('sq_ft', 'TEXT'),
        ('yr_built', 'TEXT'),
        ('last_sale', 'TEXT'),
        ('last_sale_amount', 'TEXT'),
        ('campaign', 'TEXT'),
        ('do_not_mail', 'TEXT'),
        ('property_type', 'TEXT'),
        ('bedrooms', 'TEXT'),
        ('total_bathrooms', 'TEXT'),
        ('building_sqft', 'TEXT'),
        ('lot_size_sqft', 'TEXT'),
        ('effective_year_built', 'TEXT'),
        ('total_assessed_value', 'TEXT'),
        ('last_sale_recording_date', 'TEXT'),
        ('last_sale_amount_num', 'TEXT'),
        ('total_open_loans', 'TEXT'),
        ('est_remaining_balance_open_loans', 'TEXT'),
        ('est_value', 'TEXT'),
        ('est_loan_to_value', 'TEXT'),
        ('est_equity', 'TEXT'),
        ('total_condition', 'TEXT'),
        ('interior_condition', 'TEXT'),
        ('exterior_condition', 'TEXT'),
        ('bathroom_condition', 'TEXT'),
        ('kitchen_condition', 'TEXT'),
        ('foreclosure_factor', 'TEXT'),
        ('mls_status', 'TEXT'),
        ('mls_date', 'TEXT'),
        ('mls_amount', 'TEXT'),
        ('lien_amount', 'TEXT'),
        ('current_tag', 'TEXT'),
    ],
    'property_contacts': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('property_id', 'INTEGER'),
        ('contact_id', 'INTEGER'),
        ('role', 'TEXT'),
    ],
    'property_activity_log': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('property_id', 'INTEGER'),
        ('timestamp', 'TEXT'),
        ('activity_type', 'TEXT'),
        ('details', 'TEXT'),
        ('user', 'TEXT'),
    ],
    'property_tag_history': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('property_id', 'INTEGER'),
        ('tag', 'TEXT'),
        ('changed_at', 'TEXT'),
        ('user', 'TEXT'),
    ],
    'contact_notes': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('contact_id', 'INTEGER'),
        ('value', 'TEXT'),
        ('timestamp', 'TEXT'),
    ],
    'property_notes': [
        ('id', 'INTEGER PRIMARY KEY'),
        ('property_id', 'INTEGER'),
        ('value', 'TEXT'),
        ('timestamp', 'TEXT'),
    ],
    # Add other tables as needed from models.py
}

def ensure_table(conn, table, columns):
    cur = conn.cursor()
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    exists = cur.fetchone()
    if not exists:
        col_defs = ', '.join([f'{name} {ctype}' for name, ctype in columns])
        cur.execute(f"CREATE TABLE {table} ({col_defs})")
        print(f"Created table: {table}")
    else:
        cur.execute(f"PRAGMA table_info({table})")
        existing_cols = [row[1] for row in cur.fetchall()]
        for name, ctype in columns:
            if name not in existing_cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ctype}")
                print(f"Added column {name} to {table}")
    conn.commit()

if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    for table, columns in tables.items():
        ensure_table(conn, table, columns)
    conn.close()
    print('Schema sync complete. Your database now matches models.py.')
