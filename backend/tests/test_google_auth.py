from app.api import routes
from app.core.config import settings
from app.db import get_db
from app.models import User


def test_google_auth_config_returns_public_client_id(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "petverse-client.apps.googleusercontent.com")

    response = client.get("/api/v1/auth/google/config")

    assert response.status_code == 200
    assert response.json() == {"client_id": "petverse-client.apps.googleusercontent.com"}


def test_google_login_requires_configured_client_id(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", None)

    response = client.post("/api/v1/auth/google", json={"credential": "verified-google-token"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is not configured"


def test_google_login_creates_verified_owner(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "petverse-client.apps.googleusercontent.com")
    monkeypatch.setattr(
        routes.google_id_token,
        "verify_oauth2_token",
        lambda credential, request, audience: {
            "sub": "google-user-123",
            "email": "Pet.Parent@example.com",
            "email_verified": True,
            "name": "Pet Parent",
            "aud": audience,
        },
    )

    response = client.post("/api/v1/auth/google", json={"credential": "verified-google-token"})

    assert response.status_code == 200
    result = response.json()
    assert result["user"]["email"] == "pet.parent@example.com"
    assert result["user"]["full_name"] == "Pet Parent"
    assert result["user"]["role"] == "owner"
    assert result["user"]["email_verified"] is True
    assert "password_hash" not in result["user"]
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {result['access_token']}"},
    ).status_code == 200


def test_google_login_links_verified_email_to_existing_account(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "petverse-client.apps.googleusercontent.com")
    monkeypatch.setattr(
        routes.google_id_token,
        "verify_oauth2_token",
        lambda credential, request, audience: {
            "sub": "google-user-456",
            "email": "owner@example.com",
            "email_verified": True,
        },
    )
    client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "full_name": "Pet Owner", "password": "secure-password-123"},
    )
    verification = client.app.state.test_email_outbox[0]["body"].split("?verify=")[1].split()[0]
    client.post("/api/v1/auth/verify-email", json={"token": verification})

    response = client.post("/api/v1/auth/google", json={"credential": "verified-google-token"})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"
    assert response.json()["user"]["role"] == "owner"


def test_google_login_rejects_unverified_email(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "petverse-client.apps.googleusercontent.com")
    monkeypatch.setattr(
        routes.google_id_token,
        "verify_oauth2_token",
        lambda credential, request, audience: {
            "sub": "google-user-789",
            "email": "unverified@example.com",
            "email_verified": False,
        },
    )

    response = client.post("/api/v1/auth/google", json={"credential": "verified-google-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Google must provide a verified email address"


def test_google_login_rejects_invalid_id_token(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "petverse-client.apps.googleusercontent.com")

    def reject_token(credential, request, audience):
        raise ValueError("Invalid token signature")

    monkeypatch.setattr(routes.google_id_token, "verify_oauth2_token", reject_token)

    response = client.post("/api/v1/auth/google", json={"credential": "invalid-google-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Google sign-in credential"


def test_google_login_rejects_suspended_account(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "petverse-client.apps.googleusercontent.com")
    monkeypatch.setattr(
        routes.google_id_token,
        "verify_oauth2_token",
        lambda credential, request, audience: {
            "sub": "suspended-google-user",
            "email": "suspended@example.com",
            "email_verified": True,
        },
    )
    db_generator = client.app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        db.add(User(
            email="suspended@example.com",
            full_name="Suspended User",
            password_hash="unused",
            is_suspended=True,
        ))
        db.commit()
    finally:
        db_generator.close()

    response = client.post("/api/v1/auth/google", json={"credential": "verified-google-token"})

    assert response.status_code == 403
    assert response.json()["detail"] == "This account is suspended"
