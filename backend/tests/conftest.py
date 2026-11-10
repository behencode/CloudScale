import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent / ".tmp"
_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["APP_MODE"] = "local"
os.environ["AUTH_MODE"] = "local"
os.environ["DATABASE_BACKEND"] = "sqlite"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["DESCRIPTION_PROVIDER"] = "local"
os.environ["CATEGORY_PROVIDER"] = "local"
os.environ["NOTIFICATION_BACKEND"] = "local"
os.environ["JWT_SECRET"] = "test-secret-long-enough-for-hs256-tests"
os.environ["SQLITE_PATH"] = str(_ROOT / "campusconnect.db")
os.environ["UPLOAD_DIR"] = str(_ROOT / "uploads")
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        app.state.repo.clear()
        yield test_client


def register(client, email="ada@campus.edu", name="Ada Lovelace", password="correct-horse"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password, "campus": "North Campus"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]
