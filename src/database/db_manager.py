import logging
from collections.abc import Callable

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from database.db_models import Base

logger = logging.getLogger(__name__)


class DBManager:
    """Owns one working SQLite database and supplies short-lived sessions."""

    def __init__(self):
        self.engine = None
        self._session_maker = None
        self.db_path: str | None = None

    def connect_to_db(self, db_path: str):
        self.db_path = db_path
        self.engine = create_engine(URL.create("sqlite", database=db_path))
        self._session_maker = sessionmaker(autoflush=False, bind=self.engine)
        # Older compatible saves may need tables that were introduced later.
        Base.metadata.create_all(bind=self.engine)

    def validate_database(self):
        with self.engine.connect() as connection:
            check = connection.exec_driver_sql("PRAGMA quick_check(1)").scalar()
            if check != "ok":
                raise ValueError(f"SQLite integrity check failed: {check}")
            inspector = inspect(connection)
            for table in Base.metadata.tables.values():
                actual = {column["name"] for column in inspector.get_columns(table.name)}
                missing = set(table.columns.keys()) - actual
                if missing:
                    columns = ", ".join(sorted(missing))
                    raise ValueError(f"Save table {table.name} is missing columns: {columns}")

    def get_session(self) -> Session:
        if self._session_maker is None:
            raise ConnectionError("Database not connected.")
        return self._session_maker()

    def get_session_factory(self) -> Callable[[], Session]:
        if self._session_maker is None:
            raise ConnectionError("Database not connected.")
        return self.get_session

    def disconnect(self):
        engine = self.engine
        self.engine = None
        self._session_maker = None
        self.db_path = None
        if engine is not None:
            logger.debug("Disposing of game database engine")
            engine.dispose()
