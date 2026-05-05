"""Database abstraction layer"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from phoenix.sdk.config import PhoenixConfig
from phoenix.storage.models import Base

logger = logging.getLogger(__name__)


def check_db_write_access(db_url: str) -> bool:
    """Test that we can write to the SQLite database file.

    Returns True on success; logs a clear error and returns False on failure.
    Only relevant for SQLite — always returns True for other databases.
    """
    if not db_url.startswith("sqlite"):
        return True
    # Strip the sqlite:/// prefix to get the file path
    db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if db_path in (":memory:", ""):
        return True
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("CREATE TABLE IF NOT EXISTS _healthcheck (id INTEGER PRIMARY KEY)")
        conn.execute("DELETE FROM _healthcheck")
        conn.execute("INSERT INTO _healthcheck VALUES (1)")
        conn.execute("DROP TABLE _healthcheck")
        conn.commit()
        conn.close()
        return True
    except sqlite3.OperationalError as exc:
        logger.error(
            "SQLite write access check failed for '%s': %s\n"
            "Tip: check file permissions and available disk space.\n"
            "Use --no-db flag to write results as JSON files instead.",
            db_path,
            exc,
        )
        return False


class Database:
    """Database connection and session management"""

    def __init__(self, config: PhoenixConfig):
        self.config = config
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self.db_available: bool = True
        self._initialize()

    def _initialize(self) -> None:
        """Initialize database engine and session factory, with write-access healthcheck."""
        database_url = self.config.database.url

        if not check_db_write_access(database_url):
            logger.warning(
                "Database at '%s' is not writable — DB operations will be skipped. "
                "Use --no-db flag or fix permissions to persist results.",
                database_url,
            )
            self.db_available = False
            return

        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False, "timeout": 20}
            engine_kwargs: dict = {"poolclass": StaticPool, "connect_args": connect_args}
        else:
            engine_kwargs = {
                "pool_size": self.config.database.pool_size,
                "max_overflow": self.config.database.max_overflow,
                "pool_pre_ping": True,
            }

        self.engine = create_engine(database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self) -> None:
        """Create all database tables (no-op if DB is unavailable)."""
        if not self.db_available or self.engine is None:
            logger.debug("Skipping create_tables — database is unavailable.")
            return
        try:
            Base.metadata.create_all(bind=self.engine)
        except Exception as exc:
            logger.error("Failed to create database tables: %s", exc)
            self.db_available = False

    def drop_tables(self) -> None:
        """Drop all database tables (use with caution)."""
        if not self.db_available or self.engine is None:
            return
        try:
            Base.metadata.drop_all(bind=self.engine)
        except Exception as exc:
            logger.error("Failed to drop database tables: %s", exc)

    @contextmanager
    def get_session(self):
        """Context-manager that yields a database session.

        If the database is unavailable, yields ``None`` so callers that guard
        with ``if session:`` can degrade gracefully without crashing.
        """
        if not self.db_available or self.SessionLocal is None:
            logger.debug("Database unavailable — returning null session.")
            yield None
            return

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Optional[Session]:
        """Return a raw session, or None if the DB is unavailable."""
        if not self.db_available or self.SessionLocal is None:
            return None
        return self.SessionLocal()
