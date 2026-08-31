"""
Test bootstrap. Must set dummy env vars and redirect app.db.DB_PATH to a temp
file BEFORE app.main is ever imported, since app.main calls init_db() as an
import-time side effect (against the real data/catalog.db by default).
"""
import os
import tempfile
from pathlib import Path

os.environ["R2_ACCOUNT_ID"] = "test-account"
os.environ["R2_ACCESS_KEY_ID"] = "test-key"
os.environ["R2_SECRET_ACCESS_KEY"] = "test-secret"
os.environ["R2_BUCKET_NAME"] = "test-bucket"
os.environ["API_AUTH_KEY"] = "test-api-key"
os.environ["SUBSONIC_USERNAME"] = "testuser"
os.environ["SUBSONIC_PASSWORD"] = "testpass"

import app.db as db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp()) / "bootstrap.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app as fastapi_app  # noqa: E402

API_KEY = os.environ["API_AUTH_KEY"]


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": API_KEY}


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    """A fresh, isolated, schema-initialized SQLite connection per test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    with db.get_connection() as connection:
        yield connection


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient backed by a fresh, isolated database per test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return TestClient(fastapi_app)
