import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Make the app imports discoverable in tests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DEFAULT_AI_PROVIDER"] = "mock"

from app.database.base import Base

@pytest.fixture(scope="session")
def db_engine():
    """
    Setup a session-wide SQLite database connection in memory
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Setup a function-scoped database session which rolls back 
    changes automatically after test completion
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
