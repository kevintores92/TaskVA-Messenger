import sqlite3

db_path = "messages.db"  # Update path if needed

conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("ALTER TABLE messages ADD COLUMN read INTEGER DEFAULT 0;")
    print("Column 'read' added successfully.")
except sqlite3.OperationalError as e:
    print("Error:", e)

conn.commit()
conn.close()
