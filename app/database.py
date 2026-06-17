from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import Config

# Create the declarative base class
Base = declarative_base()

# Global variables for engine and SessionLocal
engine = None
SessionLocal = None

def init_engine(database_url=None):
    """Initialize or reinitialize the SQLAlchemy engine and SessionLocal session builder."""
    global engine, SessionLocal
    url = database_url or Config.DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

# Initialize engine with the default config URL immediately upon module load
init_engine()

def init_db(database_url=None):
    """Create all tables defined in models.py."""
    eng = init_engine(database_url) if database_url else engine
    # Import models to ensure all SQLAlchemy mappings are registered on Base
    from app import models
    Base.metadata.create_all(bind=eng)

@contextmanager
def get_db():
    """Context manager to yield a db session and close it cleanly, preventing resource leaks."""
    global SessionLocal
    if SessionLocal is None:
        init_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
