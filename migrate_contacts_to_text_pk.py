import sqlite3

DB_PATH = "messages.db"  # Adjust path if needed
NEW_TABLE = "contacts_new"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Create new table with TEXT PRIMARY KEY
c.execute(f'''
CREATE TABLE IF NOT EXISTS {NEW_TABLE} (
    phone TEXT PRIMARY KEY,
    tag TEXT,
    notes TEXT,
    name TEXT,
    address TEXT
    -- Add other columns as needed, matching your schema
)
''')

# 2. Copy unique rows from old table, converting phone to TEXT
c.execute("SELECT * FROM contacts")
rows = c.fetchall()
columns = [desc[0] for desc in c.description]

insert_cols = [col for col in columns if col in ["phone", "tag", "notes", "name", "address"]]
placeholders = ", ".join(["?" for _ in insert_cols])
col_names = ", ".join(insert_cols)

for row in rows:
    row_dict = dict(zip(columns, row))
    phone_str = str(row_dict["phone"]).strip()
    # Only insert if phone is not empty
    if phone_str:
        values = [str(row_dict.get(col, "")).strip() for col in insert_cols]
        try:
            c.execute(f"INSERT OR IGNORE INTO {NEW_TABLE} ({col_names}) VALUES ({placeholders})", values)
        except Exception as e:
            print(f"Error inserting row: {e}")

conn.commit()

# 3. (Optional) Rename tables: drop old, rename new
# c.execute("DROP TABLE contacts")
# c.execute(f"ALTER TABLE {NEW_TABLE} RENAME TO contacts")
# conn.commit()

conn.close()
print("Migration complete. Review contacts_new table and rename if ready.")
