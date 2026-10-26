import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-secret-that-is-not-used-outside-tests"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import email as email_service
from app.db import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.create_all(engine)
    outbox = []
    app.state.test_email_outbox = outbox
    monkeypatch.setattr(
        email_service,
        "send_email",
        lambda recipient, subject, body: outbox.append({
            "recipient": recipient, "subject": subject, "body": body,
        }),
    )

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    del app.state.test_email_outbox
    Base.metadata.drop_all(engine)
