import os
from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["BOT_INTERNAL_SECRET"] = "test-internal-secret-with-more-than-32-characters"
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_URL"] = "http://localhost:3000"
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.models import *
from app.security import digest
from app.main import app


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    db = factory()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("app.jobs.SessionLocal", factory)
    monkeypatch.setattr("app.worker.SessionLocal", factory)
    monkeypatch.setattr("app.main.rate_limit", lambda *a, **k: None)
    monkeypatch.setattr("app.services.enqueue", lambda task: None)
    from app.config import settings

    monkeypatch.setattr(settings(), "storage_dir", tmp_path)
    db.add(
        AgentConfiguration(
            id=1,
            data={
                "price": 499,
                "trial_days": 30,
                "trial_limit": 5,
                "paid_limit": 20,
                "max_tokens": 1200,
                "temperature": 0.3,
                "timeout": 60,
                "system_prompt": "",
            },
        )
    )
    db.commit()
    yield db
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


@pytest.fixture
def client(db):
    with TestClient(app, raise_server_exceptions=True) as c:
        c.headers["origin"] = "http://localhost:3000"
        yield c


def make_user(db, token="alice", provider="google", subject=None):
    user = User(profile={"name": token}, consent_at=now(), consent_version="test")
    db.add(user)
    db.flush()
    db.add(Subscription(user_id=user.id, ends_at=now() + timedelta(days=30)))
    db.add(
        Session(
            user_id=user.id,
            token_hash=digest(token),
            expires_at=now() + timedelta(days=1),
        )
    )
    db.add(
        Identity(user_id=user.id, provider=provider, subject=subject or token, info={})
    )
    db.commit()
    return user


@pytest.fixture
def user(db, client):
    user = make_user(db)
    client.cookies.set("mama_session", "alice")
    return user
