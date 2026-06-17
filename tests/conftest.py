import os
import pytest
from app import create_app
from app.config import TestingConfig
from app.database import Base, init_db, get_db, init_engine

@pytest.fixture(scope="session")
def app():
    # Use test database URL
    test_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_water_quality.db")
    TestingConfig.DATABASE_URL = f"sqlite:///{test_db_path}"
    
    # Instantiate the application with TestingConfig
    app = create_app(TestingConfig)
    
    yield app
    
    # Cleanup test database file after session finishes
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db(app):
    # Ensure engine and tables are initialized
    init_db(app.config["DATABASE_URL"])
    with get_db() as session:
        yield session
    # Cleanup after test
    with get_db() as session:
        Base.metadata.drop_all(bind=session.get_bind())
