import os

# Must run before importing application modules. Force test defaults (do not use setdefault —
# a developer .env may already export FEATURE_*=true).
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters"
os.environ["ENCRYPTION_MASTER_KEY"] = "test-encryption-master-key-32b!!"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SEED_DEMO"] = "false"
os.environ["FEATURE_ODOO_CONNECTOR"] = "false"
os.environ["FEATURE_FAST_AI"] = "false"
os.environ["FEATURE_DEEP_RESEARCH"] = "false"
os.environ["FEATURE_SMART_RPT"] = "false"
os.environ["FEATURE_WEB_NEWS_COLLECTORS"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.auth_service import TenantService

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def demo_tenant(db_session: Session):
    tenant, owner = TenantService(db_session).create_tenant_with_owner(
        name="Coldex Demo",
        slug="coldex-demo",
        owner_email="admin@coldex-demo.example",
        owner_name="Coldex Admin",
        owner_password="ChangeMeDemo123!",
    )
    return tenant, owner


@pytest.fixture()
def other_tenant(db_session: Session):
    tenant, owner = TenantService(db_session).create_tenant_with_owner(
        name="Other Co",
        slug="other-co",
        owner_email="owner@other.example",
        owner_name="Other Owner",
        owner_password="OtherPass123!",
    )
    return tenant, owner
