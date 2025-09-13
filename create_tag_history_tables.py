"""
Script to create ContactTagHistory and PropertyTagHistory tables in the database.
Run this before migrating legacy contacts data.
"""

from models import Base, PropertyTagHistory
from sqlalchemy import create_engine

# Update this to your actual database URI
DATABASE_URL = 'postgresql://user:password@localhost:5432/messages'

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine, tables=[
    PropertyTagHistory.__table__,
])

print('Tag history tables created.')
