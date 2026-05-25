"""
Tests for authentication endpoints:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  POST /api/v1/auth/forgot-password
  POST /api/v1/auth/reset-password
"""
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.password_reset import PasswordResetToken
from app.models import User
from app.core.security import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_and_get_token(client: TestClient, email: str = "test@example.com", password: str = "securepass123") -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_success(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": "securepass123",
            "first_name": "Alice",
            "last_name": "Smith",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["first_name"] == "Alice"
    assert data["user"]["last_name"] == "Smith"
    assert "max_clips_allowed" in data["user"]


def test_register_duplicate_email(client: TestClient):
    email = "dup@example.com"
    register_and_get_token(client, email=email)
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "anotherpass123",
            "first_name": "Bob",
            "last_name": "Jones",
        },
    )
    assert resp.status_code == 400


def test_register_email_case_insensitive(client: TestClient):
    """Upper-cased email should collide with the lower-cased stored version."""
    register_and_get_token(client, email="user@email.com")
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "USER@EMAIL.COM",
            "password": "securepass123",
            "first_name": "Carol",
            "last_name": "Doe",
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success(client: TestClient):
    email = "login@example.com"
    password = "mypassword99"
    register_and_get_token(client, email=email, password=password)

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_login_wrong_password(client: TestClient):
    email = "wrongpw@example.com"
    register_and_get_token(client, email=email, password="correctpass123")

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_email(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "doesntmatter"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_authenticated(client: TestClient):
    token = register_and_get_token(client, email="logout@example.com")
    resp = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert resp.status_code == 204


def test_logout_unauthenticated(client: TestClient):
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------

def test_forgot_password_existing_email(client: TestClient):
    email = "forgot@example.com"
    register_and_get_token(client, email=email)

    with patch("app.routers.auth.send_reset_email") as mock_send:
        resp = client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert resp.status_code == 204
    mock_send.assert_called_once()


def test_forgot_password_nonexistent_email(client: TestClient):
    """Non-existent email should still return 204 to prevent enumeration."""
    with patch("app.routers.auth.send_reset_email") as mock_send:
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "ghost@example.com"},
        )

    assert resp.status_code == 204
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------

def _create_user_and_token(session: Session, email: str = "reset@example.com") -> tuple[User, PasswordResetToken]:
    """Helper that directly creates a User + valid PasswordResetToken in the test DB."""
    user = User(
        email=email,
        password_hash=hash_password("oldpassword123"),
        first_name="Reset",
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    raw_token = secrets.token_urlsafe(32)
    reset = PasswordResetToken(
        user_id=user.id,
        token=raw_token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(reset)
    session.commit()
    session.refresh(reset)

    return user, reset


def test_reset_password_valid_token(client: TestClient, session: Session):
    _, reset = _create_user_and_token(session, email="resetvalid@example.com")

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset.token, "new_password": "newpassword99"},
    )
    assert resp.status_code == 204


def test_reset_password_expired_token(client: TestClient, session: Session):
    user = User(
        email="expired@example.com",
        password_hash=hash_password("oldpassword123"),
        first_name="Exp",
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    raw_token = secrets.token_urlsafe(32)
    expired_reset = PasswordResetToken(
        user_id=user.id,
        token=raw_token,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=2),  # already expired
    )
    session.add(expired_reset)
    session.commit()

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "newpassword99"},
    )
    assert resp.status_code == 400


def test_reset_password_used_token(client: TestClient, session: Session):
    _, reset = _create_user_and_token(session, email="used@example.com")

    # First use — should succeed
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset.token, "new_password": "newpassword99"},
    )
    assert resp.status_code == 204

    # Second use with the same token — should fail
    resp2 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset.token, "new_password": "anotherpassword99"},
    )
    assert resp2.status_code == 400


def test_reset_password_invalid_token(client: TestClient):
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "totally-fake-nonexistent-token", "new_password": "newpassword99"},
    )
    assert resp.status_code == 400
