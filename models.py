from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True)
    phone = Column(String, unique=True, nullable=False)
    name = Column(String)
    tag = Column(String)
    notes = Column(Text)
    address = Column(String)
    property_details = Column(Text)
    # Add other fields as needed

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    phone = Column(String, ForeignKey('contacts.phone'))
    direction = Column(String)
    body = Column(Text)
    timestamp = Column(DateTime)
    status = Column(String)
    twilio_number = Column(String)
    contact = relationship('Contact', backref='messages')
    # Add other fields as needed

# Add other models (drip, reminders, etc.) as needed
