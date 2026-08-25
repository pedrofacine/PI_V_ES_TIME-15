import os
from unittest.mock import MagicMock, patch

# Set env vars BEFORE any app import so database.py does not raise ValueError
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-testing-only")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

# Import app with _get_pipeline mocked so YOLO never loads.
# main.py does:  from ml.scripts.process_video import _get_pipeline
# which binds the name in app.main, so we patch it there too.
with patch("ml.scripts.process_video._get_pipeline", return_value=MagicMock()):
    from app.main import app
    from app.core.database import get_session


@pytest.fixture(name="engine")
def engine_fixture():
    """Fresh SQLite in-memory engine with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    """SQLModel Session bound to the test engine."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """
    FastAPI TestClient with:
    - get_session dependency overridden to use the test SQLite session
    - _get_pipeline mocked so YOLO is never loaded during TestClient startup
    """
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override

    with patch("app.main._get_pipeline", return_value=MagicMock()):
        with patch("app.main.create_db_and_tables", return_value=None):
            with TestClient(app, raise_server_exceptions=True) as client:
                yield client

    app.dependency_overrides.clear()
