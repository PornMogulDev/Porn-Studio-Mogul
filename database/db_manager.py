import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

from database.db_models import Base

class DBManager:
    """Handles SQLAlchemy engine and session creation for a given database file."""
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.db_path = None

    def connect_to_db(self, db_path: str):
        """Connects to a specific SQLite database file."""
        self.db_path = db_path
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # Ensure the schema exists if the file is new/empty, but don't drop existing data.
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Returns a new database session."""
        if not self.SessionLocal:
            raise ConnectionError("Database not connected. Call connect_to_db first.")
        return self.SessionLocal()

    def create_database(self, db_path: str):
        """Creates a new, empty database file with the required schema."""
        # Ensure the directory exists
        Path(db_path).parent.mkdir(exist_ok=True)
        # If file exists, remove it to ensure a fresh start
        if os.path.exists(db_path):
            os.remove(db_path)
            
        self.connect_to_db(db_path)
        # The connection logic already handles schema creation
        
    def disconnect(self):
        """Disposes of the engine connection."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.SessionLocal = None
            self.db_path = None