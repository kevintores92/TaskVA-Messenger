import sqlite3

DB_PATH = "messages.db"  # Update path if needed

def create_contacts_new():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS contacts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT UNIQUE,
            address TEXT,
            tag TEXT,
            notes TEXT,
            type TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("contacts_new table created or already exists.")

if __name__ == "__main__":
    create_contacts_new()