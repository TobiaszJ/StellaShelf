"""API endpoint tests using FastAPI TestClient with temporary database."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stellashelf.api import app, set_db_path
from stellashelf.db import init_db

TEST_API_KEY = "test-api-key-for-testing"


@pytest.fixture(autouse=True)
def set_test_api_key():
    os.environ["STELLASHELF_API_KEY"] = TEST_API_KEY
    # Force reload API key from env
    from stellashelf.api import _load_or_generate_api_key

    _load_or_generate_api_key()
    yield


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine, SessionLocal = init_db(db_path)
        set_db_path(db_path)
        with TestClient(app) as c:
            yield c


def auth_headers():
    return {"X-API-Key": TEST_API_KEY}


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestScan:
    def test_scan_invalid_path(self, client):
        resp = client.post(
            "/api/v1/scan", json={"path": "/nonexistent/path"}, headers=auth_headers()
        )
        assert resp.status_code == 404

    def test_scan_status(self, client):
        resp = client.get("/api/v1/scan/status")
        assert resp.status_code == 200


class TestTargets:
    def test_list_targets(self, client):
        resp = client.get("/api/v1/targets")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 0

    def test_get_target_not_found(self, client):
        resp = client.get("/api/v1/targets/999")
        assert resp.status_code == 404


class TestSessions:
    def test_list_sessions(self, client):
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200

    def test_update_session_not_found(self, client):
        resp = client.patch("/api/v1/sessions/999", json={"status": "raw"}, headers=auth_headers())
        assert resp.status_code == 404

    def test_update_session_bad_status(self, client):
        resp = client.patch(
            "/api/v1/sessions/1", json={"status": "INVALID"}, headers=auth_headers()
        )
        assert resp.status_code == 400


class TestFrames:
    def test_list_frames(self, client):
        resp = client.get("/api/v1/frames")
        assert resp.status_code == 200

    def test_get_frame_not_found(self, client):
        resp = client.get("/api/v1/frames/999")
        assert resp.status_code == 404


class TestEquipment:
    def test_list_cameras(self, client):
        resp = client.get("/api/v1/cameras")
        assert resp.status_code == 200

    def test_list_telescopes(self, client):
        resp = client.get("/api/v1/telescopes")
        assert resp.status_code == 200

    def test_list_filters(self, client):
        resp = client.get("/api/v1/filters")
        assert resp.status_code == 200


class TestSettings:
    def test_list_settings(self, client):
        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200

    def test_get_stats(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200


class TestGeneral:
    def test_cors_headers(self, client):
        resp = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200


class TestAuth:
    def test_mutation_requires_api_key(self, client):
        """POST endpoints should return 401 without API key."""
        resp = client.post("/api/v1/settings", json=[])
        assert resp.status_code == 401

    def test_invalid_api_key_rejected(self, client):
        """POST with invalid API key should return 403."""
        resp = client.post("/api/v1/settings", json=[], headers={"X-API-Key": "invalid-key"})
        assert resp.status_code == 403

    def test_valid_api_key_accepted(self, client):
        """POST with valid API key should succeed (may still have other errors)."""
        resp = client.post("/api/v1/settings", json=[], headers=auth_headers())
        assert resp.status_code in (200, 422)
