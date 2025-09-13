"""
Distribute legacy contacts table data to normalized schema in messages.db.
- Phones → phones table
- Owner/mailing → contacts_new
- Property info/tags → properties (current_tag)
- Notes → property_notes (linked to property)
"""
import sqlite3

DB_PATH = 'messages.db'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Fetch all legacy contacts
cur.execute('SELECT * FROM contacts')
rows = cur.fetchall()
columns = [desc[0] for desc in cur.description]

for row in rows:
    data = dict(zip(columns, row))
    # --- Classification ---
    if 'contacts_no_name' not in locals():
        contacts_no_name = []
    if 'contacts_no_address' not in locals():
        contacts_no_address = []
    if 'contacts_no_name_or_address' not in locals():
        contacts_no_name_or_address = []
    # Assign 'Unknown' for missing name/address
    first_name = (data.get('Owner 1 First Name') or '').strip()
    last_name = (data.get('Owner 1 Last Name') or '').strip()
    address_val = (data.get('address') or '').strip()
    if not first_name and not last_name:
        first_name = 'Unknown'
        last_name = f"#{row[0]}"
    elif not first_name:
        first_name = 'Unknown'
    elif not last_name:
        last_name = 'Unknown'
    if not address_val:
        address_val = f"Unknown #{row[0]}"
    has_name = bool(first_name or last_name)
    has_address = bool(address_val)
    if not has_name and not has_address:
        contacts_no_name_or_address.append(data)
    elif not has_name:
        contacts_no_name.append(data)
    elif not has_address:
        contacts_no_address.append(data)
    # --- Phones ---
    phone_fields = [
        ('phone', 'Line Type'),
        ('Alt Phone 1', 'Alt Line Type 1'),
        ('Alt Phone 2', 'Alt Line Type 2'),
    ]
    phone_ids = []
    for phone_col, type_col in phone_fields:
        phone_val = str(data.get(phone_col, '')).strip()
        if phone_val:
            cur.execute('INSERT OR IGNORE INTO phones (phone) VALUES (?)', (phone_val,))
            cur.execute('SELECT id FROM phones WHERE phone=?', (phone_val,))
            phone_id = cur.fetchone()[0]
            phone_ids.append(phone_id)
    # --- ContactsNew ---
    if 'inserted_phones' not in locals():
        inserted_phones = set()
    mailing_care_of_name = data.get('Mailing Care of Name', '')
    mailing_street_address = data.get('Mailing Street Address', '')
    mailing_unit = data.get('Mailing Unit', '')
    mailing_city = data.get('Mailing City', '')
    mailing_state = data.get('Mailing State', '')
    mailing_zip = str(data.get('Mailing Zip', ''))
    mailing_county = str(data.get('Mailing County', ''))
    contact_insert = (
        first_name, last_name, phone_val, address_val, mailing_care_of_name,
        mailing_street_address, mailing_unit, mailing_city, mailing_state, mailing_zip, mailing_county, '', '', ''
    )
    # Prevent duplicate phone inserts in this batch
    if 'duplicate_rows' not in locals():
        duplicate_rows = []
    if phone_val and phone_val in inserted_phones:
        # Log duplicate row for review
        duplicate_rows.append(data)
        cur.execute('SELECT id FROM contacts_new WHERE phone=?', (phone_val,))
        existing_contact = cur.fetchone()
        contact_id = existing_contact[0] if existing_contact else None
    else:
        cur.execute('SELECT id FROM contacts_new WHERE phone=?', (phone_val,))
        existing_contact = cur.fetchone()
        if existing_contact:
            # Log duplicate row for review
            duplicate_rows.append(data)
            contact_id = existing_contact[0]
        else:
            cur.execute('''INSERT INTO contacts_new (
                first_name, last_name, phone, address, mailing_care_of_name,
                mailing_street_address, mailing_unit, mailing_city, mailing_state, mailing_zip, mailing_county, type, tag, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', contact_insert)
            contact_id = cur.lastrowid
            if phone_val:
                inserted_phones.add(phone_val)
    # Link phones to contact
    for phone_id in phone_ids:
        cur.execute('INSERT INTO contact_phones (contact_id, phone_id) VALUES (?, ?)', (contact_id, phone_id))
    # --- Properties ---
    prop_insert = (
        address_val, data.get('Unit', ''), data.get('city', ''), data.get('state', ''), str(data.get('zip', '')),
        data.get('county', ''), data.get('Zillow Link', ''), data.get('bd/ba', ''), str(data.get('sq ft', '')), str(data.get('yr-built', '')),
        data.get('last-sale', ''), data.get('last-sale-amount', ''), data.get('Campaign', ''), data.get('Do Not Mail', ''), data.get('Property Type', ''),
        str(data.get('Bedrooms', '')), str(data.get('Total Bathrooms', '')), str(data.get('Building Sqft', '')), str(data.get('Lot Size Sqft', '')),
        str(data.get('Effective Year Built', '')), str(data.get('Total Assessed Value', '')), data.get('Last Sale Recording Date', ''), str(data.get('Last Sale Amount', '')),
        str(data.get('Total Open Loans', '')), str(data.get('Est. Remaining balance of Open Loans', '')), str(data.get('Est. Value', '')), str(data.get('Est. Loan-to-Value', '')),
        str(data.get('Est. Equity', '')), data.get('Total Condition', ''), data.get('Interior Condition', ''), data.get('Exterior Condition', ''),
        data.get('Bathroom Condition', ''), data.get('Kitchen Condition', ''), data.get('Foreclosure Factor', ''), data.get('MLS Status', ''),
        data.get('MLS Date', ''), str(data.get('MLS Amount', '')), str(data.get('Lien Amount', '')), data.get('tag', ''), # current_tag
    )
    cur.execute('''INSERT INTO properties (
        address, unit, city, state, zip, county, zillow_link, bd_ba, sq_ft, yr_built, last_sale, last_sale_amount, campaign,
        do_not_mail, property_type, bedrooms, total_bathrooms, building_sqft, lot_size_sqft, effective_year_built, total_assessed_value,
        last_sale_recording_date, last_sale_amount_num, total_open_loans, est_remaining_balance_open_loans, est_value, est_loan_to_value,
        est_equity, total_condition, interior_condition, exterior_condition, bathroom_condition, kitchen_condition, foreclosure_factor,
        mls_status, mls_date, mls_amount, lien_amount, current_tag
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', prop_insert)
    property_id = cur.lastrowid
    # --- Notes ---
    notes = data.get('notes', '')
    if notes:
        cur.execute('INSERT INTO property_notes (property_id, value, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)', (property_id, notes))

conn.commit()
conn.close()
print('Contacts distributed to new schema.')
if 'duplicate_rows' in locals() and duplicate_rows:
    print(f"\nDuplicate phone rows not inserted ({len(duplicate_rows)}):")
    for dup in duplicate_rows:
        print(dup)
if 'contacts_no_name' in locals() and contacts_no_name:
    print(f"\nContacts with no name ({len(contacts_no_name)}):")
    for cnn in contacts_no_name:
        print(cnn)
if 'contacts_no_address' in locals() and contacts_no_address:
    print(f"\nContacts with no address ({len(contacts_no_address)}):")
    for cna in contacts_no_address:
        print(cna)
if 'contacts_no_name_or_address' in locals() and contacts_no_name_or_address:
    print(f"\nContacts with no name or address ({len(contacts_no_name_or_address)}):")
    for cnna in contacts_no_name_or_address:
        print(cnna)
