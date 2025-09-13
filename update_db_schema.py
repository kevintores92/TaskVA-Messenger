import sqlite3

DB_PATH = 'messages.db'

def drop_and_rename_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Drop the old contacts table if it exists
    cur.execute('DROP TABLE IF EXISTS contacts')
    # Rename contacts_new to contacts
    cur.execute('ALTER TABLE contacts_new RENAME TO contacts')
    conn.commit()
    conn.close()
    print('Dropped contacts table and renamed contacts_new to contacts.')

if __name__ == '__main__':
    drop_and_rename_tables()
