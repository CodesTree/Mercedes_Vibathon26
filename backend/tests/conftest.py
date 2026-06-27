import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event as sa_event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.seed import seed

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

# StaticPool ensures all connections share the same in-memory database.
# Without it, each new SQLAlchemy connection gets a fresh empty in-memory DB,
# causing "no such table" errors on refresh/lazy-load operations.
engine_test = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@sa_event.listens_for(engine_test, "connect")
def set_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA busy_timeout = 5000")
    cur.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(autouse=True)
def db_session():
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    seed(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def client(db_session):
    async def mock_poller():
        await asyncio.sleep(9999)  # hang forever, cancelled on shutdown

    # Mock init_db and seed in the lifespan so they don't use the real engine/db.
    # Our db_session fixture already creates the schema and seeds via the test engine.
    with patch("app.main.run_poller", mock_poller), \
         patch("app.main.init_db", return_value=None), \
         patch("app.main.seed", return_value=None):
        with TestClient(app) as c:
            yield c
