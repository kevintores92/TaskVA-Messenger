import sqlite3

DB_PATH = "messages.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Drop old contacts table
c.execute("DROP TABLE IF EXISTS contacts")

# Rename contacts_new to contacts
c.execute("ALTER TABLE contacts_new RENAME TO contacts")

conn.commit()
conn.close()
print("Renamed contacts_new to contacts. Migration complete!")