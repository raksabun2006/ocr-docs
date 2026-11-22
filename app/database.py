"""
Database Engine & Session Management
Khmer Government Document Intelligence System

Configures SQLAlchemy 2.0 with connection pooling and session management.
Supports PostgreSQL (with psycopg driver) and automatic SQLite fallback for local development.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

logger = logging.getLogger("database")

Base = declarative_base()

def get_engine():
    """Initializes the database engine with PostgreSQL or SQLite fallback."""
    db_url = settings.DATABASE_URL
    try:
        if db_url.startswith("postgresql"):
            # Test engine connection
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 2}
            )
            # Try connecting
            with engine.connect():
                logger.info("Connected successfully to PostgreSQL database.")
                return engine
    except Exception as exc:
        logger.warning(f"PostgreSQL connection failed ({exc}).")
        if settings.DB_FALLBACK_SQLITE:
            logger.info("Falling back to local SQLite database for development.")
            return create_engine(
                settings.SQLITE_URL,
                connect_args={"check_same_thread": False}
            )
        raise

    # If SQLite configured directly
    return create_engine(
        settings.SQLITE_URL,
        connect_args={"check_same_thread": False}
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Creates all database tables defined in models."""
    import app.models  # Ensure models are imported
    Base.metadata.create_all(bind=engine)

def get_db():
    """FastAPI Dependency for database session injection with automatic cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
