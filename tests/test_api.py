"""API endpoint tests using FastAPI TestClient with temporary database."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stellashelf.api import app, set_db_path
from stellashelf.db import init_db


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine, SessionLocal = init_db(db_path)
        set_db_path(db_path)
        with TestClient(app) as c:
            yield c


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "db" in data


class TestTargets:
    def test_list_targets_empty(self, client):
        resp = client.get("/api/v1/targets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_target_types_empty(self, client):
        resp = client.get("/api/v1/targets/types")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object_types"] == []
        assert data["constellations"] == []

    def test_get_target_not_found(self, client):
        resp = client.get("/api/v1/targets/999")
        assert resp.status_code == 404


class TestFrames:
    def test_list_frames_empty(self, client):
        resp = client.get("/api/v1/frames")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_frame_not_found(self, client):
        resp = client.get("/api/v1/frames/999")
        assert resp.status_code == 404


class TestSessions:
    def test_list_sessions_empty(self, client):
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_session_not_found(self, client):
        resp = client.get("/api/v1/sessions/999")
        assert resp.status_code == 404

    def test_session_stats_not_found(self, client):
        resp = client.get("/api/v1/sessions/999/stats")
        assert resp.status_code == 404

    def test_update_session_not_found(self, client):
        resp = client.patch("/api/v1/sessions/999", json={"status": "raw"})
        assert resp.status_code == 404

    def test_update_session_invalid_status(self, client):
        resp = client.patch("/api/v1/sessions/1", json={"status": "invalid"})
        assert resp.status_code == 400


class TestDashboard:
    def test_dashboard_empty(self, client):
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_targets"] == 0
        assert data["total_frames"] == 0
        assert data["total_sessions"] == 0


class TestSearch:
    def test_search_empty(self, client):
        resp = client.get("/api/v1/search", params={"q": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["targets"] == []
        assert data["sessions"] == []
        assert data["frames"] == []

    def test_search_requires_query(self, client):
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422


class TestScan:
    def test_scan_status_idle(self, client):
        resp = client.get("/api/v1/scan/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "idle"
        assert data["running"] is False

    def test_scan_path_not_found(self, client):
        resp = client.post("/api/v1/scan", json={"path": "/nonexistent/path"})
        assert resp.status_code == 404


class TestEquipment:
    def test_list_cameras_empty(self, client):
        resp = client.get("/api/v1/cameras")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_telescopes_empty(self, client):
        resp = client.get("/api/v1/telescopes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filters_empty(self, client):
        resp = client.get("/api/v1/filters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_duplicates_empty(self, client):
        resp = client.get("/api/v1/targets/duplicates")
        assert resp.status_code == 200
        assert resp.json() == []


class TestStats:
    def test_stats_empty(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["targets"] == 0
        assert data["frames"] == 0
        assert data["sessions"] == 0
        assert data["cameras"] == 0
        assert data["telescopes"] == 0


class TestSettings:
    def test_list_settings_empty(self, client):
        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_and_list_settings(self, client):
        resp = client.post(
            "/api/v1/settings",
            json=[{"key": "test_key", "value": "test_value", "description": "A test setting"}],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "test_key"
        assert data[0]["value"] == "test_value"


class TestMerge:
    def test_merge_same_target(self, client):
        resp = client.post("/api/v1/targets/merge", json={"source_id": 1, "destination_id": 1})
        assert resp.status_code == 400

    def test_merge_nonexistent(self, client):
        resp = client.post("/api/v1/targets/merge", json={"source_id": 1, "destination_id": 2})
        assert resp.status_code == 404

    def test_merge_group_no_duplicates(self, client):
        resp = client.post(
            "/api/v1/targets/merge-group", json={"canonical_name": "M 51"}
        )
        assert resp.status_code == 400


class TestCleanup:
    def test_cleanup_orphans_empty(self, client):
        resp = client.post("/api/v1/db/cleanup-orphans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_reset_without_confirm(self, client):
        resp = client.post("/api/v1/db/reset", json={"confirm": False})
        assert resp.status_code == 400

    def test_reset_db(self, client):
        resp = client.post("/api/v1/db/reset", json={"confirm": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestFramesDelete:
    def test_delete_no_ids(self, client):
        resp = client.post("/api/v1/frames/delete", json={"frame_ids": []})
        assert resp.status_code == 400

    def test_delete_nonexistent(self, client):
        resp = client.post("/api/v1/frames/delete", json={"frame_ids": [999]})
        assert resp.status_code == 404


class TestPlatesolve:
    def test_platesolve_status_idle(self, client):
        resp = client.get("/api/v1/platesolve/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "idle"
        assert data["running"] is False

    def test_platesolve_cancel(self, client):
        resp = client.post("/api/v1/platesolve/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelling"


class TestVersion:
    def test_app_version(self, client):
        from stellashelf import __version__
        assert app.version == __version__
