import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

from database.db_models import Base

logger = logging.getLogger(__name__)

class DBManager:
    """
    Handles SQLAlchemy engine and session creation for a given database file.
    
    This manager provides two ways to work with sessions:
    1. get_session() - Returns a new session instance (for one-off operations)
    2. get_session_factory() - Returns the sessionmaker factory (for services)
    
    Services should use get_session_factory() and create sessions as needed
    for each operation to ensure proper transaction boundaries.
    """
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.db_path = None

    def connect_to_db(self, db_path: str):
        """Connects to a specific SQLite database file and creates the sessionmaker."""
        self.db_path = db_path
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # Ensure the schema exists if the file is new/empty, but don't drop existing data.
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """
        Returns a new database session instance.
        
        Use this for one-off operations. For services that need multiple
        operations, use get_session_factory() instead.
        """
        if not self.SessionLocal:
            raise ConnectionError("Database not connected. Call connect_to_db first.")
        return self.SessionLocal()
    
    def get_session_factory(self):
        """
        Returns the sessionmaker factory for creating sessions.
        
        Services should store this factory and call it to create new sessions
        for each operation. This ensures proper transaction boundaries and
        prevents session sharing issues.
        
        Example:
            session_factory = db_manager.get_session_factory()
            session = session_factory()  # Create new session
            try:
                # Do work
                session.commit()
            except:
                session.rollback()
            finally:
                session.close()
        """
        if not self.SessionLocal:
            raise ConnectionError("Database not connected. Call connect_to_db first.")
        return self.SessionLocal

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
            logger.debug(f"Disposing of engine for database: {self.db_path}")
            self.engine.dispose() # This is the crucial step to close all connections
            self.engine = None
            self.session_factory = None
            self.db_path = None