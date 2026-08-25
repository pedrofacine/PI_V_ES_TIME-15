"""
Tests for job endpoints:
  POST /api/v1/jobs/
  GET  /api/v1/jobs/{id}/stream
  POST /api/v1/jobs/{id}/confirm
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.modules.identity.models import User
from app.models import Video, ProcessingJob
from app.core.security import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_and_get_token(client: TestClient, email: str = "job_test@example.com", password: str = "securepass123") -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Job",
            "last_name": "Tester",
        },
    )
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_user_video_job(session: Session, status: str = "WAITING_USER") -> tuple[User, Video, ProcessingJob]:
    """Directly create User + Video + ProcessingJob in the test DB."""
    user = User(
        email=f"jobowner_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
        first_name="Owner",
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    video = Video(
        user_id=user.id,
        original_filename="test.mp4",
        storage_path="/tmp/test.mp4",
        file_size_mb=1.0,
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    job = ProcessingJob(
        video_id=video.id,
        target_number=10,
        status=status,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    return user, video, job


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/ — create_job
# ---------------------------------------------------------------------------

def test_create_job_unauthenticated(client: TestClient):
    """Uploading without a token must be rejected."""
    resp = client.post(
        "/api/v1/jobs/",
        data={"target_number": "10", "start_ts": "0", "end_ts": "0"},
        files={"video": ("test.mp4", b"fake video bytes", "video/mp4")},
    )
    assert resp.status_code in (401, 403)


def test_create_job_success(client: TestClient):
    """Valid upload + auth token returns 202 with job_id and PENDING status."""
    token = register_and_get_token(client, email="createjob@example.com")

    with patch("app.routers.jobs.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        response = client.post(
            "/api/v1/jobs/",
            data={"target_number": "10", "start_ts": "0", "end_ts": "0"},
            files={"video": ("test.mp4", b"fake video bytes", "video/mp4")},
            headers=auth_headers(token),
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    # Thread was started (not a real background call)
    mock_thread.return_value.start.assert_called_once()


def test_create_job_invalid_number_negative(client: TestClient):
    """target_number < 0 must fail with 422 (Pydantic/FastAPI validation)."""
    token = register_and_get_token(client, email="negnum@example.com")

    with patch("app.routers.jobs.threading.Thread"):
        response = client.post(
            "/api/v1/jobs/",
            data={"target_number": "-1", "start_ts": "0", "end_ts": "0"},
            files={"video": ("test.mp4", b"fake video bytes", "video/mp4")},
            headers=auth_headers(token),
        )

    assert response.status_code == 422


def test_create_job_invalid_number_too_large(client: TestClient):
    """target_number > 999 must fail with 422 (Pydantic/FastAPI validation)."""
    token = register_and_get_token(client, email="bignum@example.com")

    with patch("app.routers.jobs.threading.Thread"):
        response = client.post(
            "/api/v1/jobs/",
            data={"target_number": "1000", "start_ts": "0", "end_ts": "0"},
            files={"video": ("test.mp4", b"fake video bytes", "video/mp4")},
            headers=auth_headers(token),
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{id}/confirm — confirm_player
# ---------------------------------------------------------------------------

def test_confirm_player_job_not_found(client: TestClient):
    """Non-existent job UUID must return 404."""
    random_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/jobs/{random_id}/confirm",
        json={"candidate_signature": "10_#ff0000", "start_ts": 0, "end_ts": 0},
    )
    assert resp.status_code == 404


def test_confirm_player_wrong_status(client: TestClient, session: Session):
    """Job in COMPLETED status must return 400 (no more confirmations accepted)."""
    _, _, job = _create_user_video_job(session, status="COMPLETED")

    with patch("app.routers.jobs.threading.Thread"):
        resp = client.post(
            f"/api/v1/jobs/{job.id}/confirm",
            json={"candidate_signature": "10_#ff0000", "start_ts": 0, "end_ts": 0},
        )

    assert resp.status_code == 400


def test_confirm_player_success(client: TestClient, session: Session):
    """Job in WAITING_USER status with a valid signature returns 200 and status TRACKING."""
    _, _, job = _create_user_video_job(session, status="WAITING_USER")

    with patch("app.routers.jobs.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post(
            f"/api/v1/jobs/{job.id}/confirm",
            json={"candidate_signature": "10_#ff0000", "start_ts": 0, "end_ts": 0},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "TRACKING"
    mock_thread.return_value.start.assert_called_once()

    # Verify the DB record was updated
    session.refresh(job)
    assert job.status == "TRACKING"


def test_confirm_player_fast_scan_status(client: TestClient, session: Session):
    """Job in FAST_SCAN status (user clicked early) also accepts confirmation."""
    _, _, job = _create_user_video_job(session, status="FAST_SCAN")

    with patch("app.routers.jobs.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post(
            f"/api/v1/jobs/{job.id}/confirm",
            json={"candidate_signature": "10_#ff0000", "start_ts": 0, "end_ts": 0},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "TRACKING"


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{id}/stream — stream_job_status
# ---------------------------------------------------------------------------

def test_stream_job_status_not_found(client: TestClient, engine):
    """
    Streaming a non-existent job UUID returns an SSE response whose first
    data payload contains an 'error' key.

    stream_job_status opens `Session(engine)` directly from app.routers.jobs
    (bypassing the dependency-injected test session).  We patch that engine
    reference so it uses the test engine, ensuring the job lookup returns None.
    """
    random_id = str(uuid.uuid4())

    with patch("app.routers.jobs.engine", engine):
        resp = client.get(f"/api/v1/jobs/{random_id}/stream")

    # The endpoint returns a StreamingResponse regardless; check first chunk.
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/event-stream")

    body = resp.text
    # First SSE chunk should contain the error payload
    assert "error" in body


def test_stream_job_status_found(client: TestClient, session: Session, engine):
    """
    Streaming an existing COMPLETED job returns a payload with job_id and status.
    The generator exits after one iteration because status is COMPLETED/done.
    """
    _, _, job = _create_user_video_job(session, status="COMPLETED")

    with patch("app.routers.jobs.engine", engine):
        resp = client.get(f"/api/v1/jobs/{job.id}/stream")

    assert resp.status_code == 200
    body = resp.text
    assert str(job.id) in body
    assert "COMPLETED" in body
