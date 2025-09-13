from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# --- Notes, Tag History, and Call Log History Tables ---
from datetime import datetime



class PropertyTagHistory(Base):
    __tablename__ = 'property_tag_history'
    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey('properties.id'))
    tag = Column(String)
    changed_at = Column(DateTime, default=datetime.utcnow)
    user = Column(String, nullable=True)
class ContactNote(Base):
    __tablename__ = 'contact_notes'
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts_new.id'))
    value = Column(Text)
    timestamp = Column(DateTime)

class PropertyNote(Base):
    __tablename__ = 'property_notes'
    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey('properties.id'))
    value = Column(Text)
    timestamp = Column(DateTime)

class CallLog(Base):
    __tablename__ = 'call_logs'
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts_new.id'))
    phone_id = Column(Integer, ForeignKey('phones.id'))
    property_id = Column(Integer, ForeignKey('properties.id'), nullable=True)
    timestamp = Column(DateTime)
    duration = Column(Integer)  # seconds
    notes = Column(Text)

class ContactNew(Base):
    __tablename__ = 'contacts_new'
    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    address = Column(String)
    mailing_care_of_name = Column(String)
    mailing_street_address = Column(String)
    mailing_unit = Column(String)
    mailing_city = Column(String)
    mailing_state = Column(String)
    mailing_zip = Column(String)
    mailing_county = Column(String)
    type = Column(String)

class Phone(Base):
    __tablename__ = 'phones'
    id = Column(Integer, primary_key=True)
    phone = Column(String, unique=True, nullable=False)

class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    address = Column(String)
    mailing_care_of_name = Column(String)
    mailing_street_address = Column(String)
    mailing_unit = Column(String)
    mailing_city = Column(String)
    mailing_state = Column(String)
    mailing_zip = Column(String)
    mailing_county = Column(String)
    type = Column(String)
    zillow_link = Column(String)
    bd_ba = Column(String)
    sq_ft = Column(String)
    yr_built = Column(String)
    last_sale = Column(String)
    last_sale_amount = Column(String)
    campaign = Column(String)
    do_not_mail = Column(String)
    property_type = Column(String)
    bedrooms = Column(String)
    total_bathrooms = Column(String)
    building_sqft = Column(String)
    lot_size_sqft = Column(String)
    effective_year_built = Column(String)
    total_assessed_value = Column(String)
    last_sale_recording_date = Column(String)
    last_sale_amount_num = Column(String)
    total_open_loans = Column(String)
    est_remaining_balance_open_loans = Column(String)
    est_value = Column(String)
    est_loan_to_value = Column(String)
    est_equity = Column(String)
    total_condition = Column(String)
    interior_condition = Column(String)
    exterior_condition = Column(String)
    bathroom_condition = Column(String)
    kitchen_condition = Column(String)
    foreclosure_factor = Column(String)
    mls_status = Column(String)
    mls_date = Column(String)
    mls_amount = Column(String)
    lien_amount = Column(String)
    current_tag = Column(String)  # Current tag for property
    __table_args__ = (UniqueConstraint('street_address', 'unit', 'city', 'state', 'zip', name='_property_uc'),)

class PropertyContact(Base):
    __tablename__ = 'property_contacts'
    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey('properties.id'))
    contact_id = Column(Integer, ForeignKey('contacts_new.id'))
    role = Column(String)

class PropertyActivityLog(Base):
    __tablename__ = 'property_activity_log'
    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey('properties.id'))
    timestamp = Column(DateTime)
    activity_type = Column(String)
    details = Column(Text)
    user = Column(String)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    phone = Column(String)
    direction = Column(String)
    body = Column(Text)
    timestamp = Column(DateTime)
    status = Column(String)
    twilio_number = Column(String)
    contact_id = Column(Integer, ForeignKey('contacts_new.id'))

# --- Drip, Reminders, Campaigns ---
class DripAutomation(Base):
    __tablename__ = 'drip_automations'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class DripMessage(Base):
    __tablename__ = 'drip_messages'
    id = Column(Integer, primary_key=True)
    drip_id = Column(Integer, ForeignKey('drip_automations.id'))
    day_offset = Column(Integer)
    message_template = Column(Text)

class ContactDripAssignment(Base):
    __tablename__ = 'contact_drip_assignments'
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts_new.id'))
    drip_id = Column(Integer, ForeignKey('drip_automations.id'))
    assigned_at = Column(DateTime)
    completed = Column(Boolean)

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True)
    thread_phone = Column(String)
    remind_at = Column(DateTime)
    note = Column(Text)

class Campaign(Base):
    __tablename__ = 'campaigns'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime)
    total_rows = Column(Integer)

class CampaignRow(Base):
    __tablename__ = 'campaign_rows'
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'))
    created_at = Column(DateTime)

class CampaignRowData(Base):
    __tablename__ = 'campaign_row_data'
    row_id = Column(Integer, primary_key=True)
    campaign_row_id = Column(Integer, ForeignKey('campaign_rows.id'))
    key = Column(String)
    value = Column(Text)