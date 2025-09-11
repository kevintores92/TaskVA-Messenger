import sqlite3

DB_PATH = r"C:\Users\admin\Desktop\ACE\Ace Messenger\Messenger\messages.db"

def create_flexible_import_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Campaigns table
    c.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_rows INTEGER DEFAULT 0
        )
    ''')
    # Each imported row
    c.execute('''
        CREATE TABLE IF NOT EXISTS campaign_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
        )
    ''')
    # Key-value pairs for each row
    c.execute('''
        CREATE TABLE IF NOT EXISTS campaign_row_data (
            row_id INTEGER,
            key TEXT,
            value TEXT,
            FOREIGN KEY(row_id) REFERENCES campaign_rows(id)
        )
    ''')
    conn.commit()
    conn.close()
    print("Flexible campaign import tables created successfully.")

if __name__ == "__main__":
    create_flexible_import_tables()
