import sqlite3

DB_PATH = r'C:\Users\admin\Desktop\ACE\Ace Messenger\Messenger\messages.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('''SELECT * FROM messages ORDER BY timestamp ASC''')
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
