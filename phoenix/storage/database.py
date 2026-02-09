"""Database abstraction layer"""

from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager

from phoenix.sdk.config import PhoenixConfig
from phoenix.storage.models import Base


class Database:
    """Database connection and session management"""

    def __init__(self, config: PhoenixConfig):
        """
        Initialize database connection.
        
        Args:
            config: Phoenix configuration
        """
        self.config = config
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialize()

    def _initialize(self):
        """Initialize database engine and session factory"""
        database_url = self.config.database.url
        
        # SQLite-specific configuration
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {
                "check_same_thread": False,
                "timeout": 20
            }
            # Use StaticPool for SQLite to allow multiple connections
            engine_kwargs = {
                "poolclass": StaticPool,
                "connect_args": connect_args
            }
        else:
            # PostgreSQL configuration
            engine_kwargs = {
                "pool_size": self.config.database.pool_size,
                "max_overflow": self.config.database.max_overflow,
                "pool_pre_ping": True,  # Verify connections before using
            }

        self.engine = create_engine(database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all database tables (use with caution)"""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self):
        """
        Get a database session context manager.
        
        Usage:
            with db.get_session() as session:
                # Use session
                pass
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """
        Get a database session directly (caller must manage lifecycle).
        
        Returns:
            Database session
        """
        return self.SessionLocal()
