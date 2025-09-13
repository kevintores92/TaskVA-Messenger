import os
from sqlalchemy import create_engine
from models import Base
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL') or 'postgresql://postgres:[YOUR-PASSWORD]@db.jtoseniheciluqtthrwj.supabase.co:5432/postgres'

def migrate():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print('Database tables created!')

if __name__ == '__main__':
    migrate()
