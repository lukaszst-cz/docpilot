from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import connect, init_db
from docpilot.db_maintenance import create_database_checkpoint, list_recovery_points


def test_verified_checkpoint_preserves_committed_database_state(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)

    with connect(settings) as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('checkpoint-test','before')")

    point = create_database_checkpoint(db_path)
    checkpoint_path = settings.state / "recovery" / point["name"]

    assert point["kind"] == "checkpoint"
    assert point["integrity"] == "ok"
    assert checkpoint_path.exists()

    with sqlite3.connect(checkpoint_path) as checkpoint:
        assert checkpoint.execute(
            "SELECT value FROM settings WHERE key='checkpoint-test'"
        ).fetchone()[0] == "before"


def test_manual_recovery_points_are_pruned_to_five(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)

    for index in range(7):
        with connect(settings) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES('checkpoint-sequence',?)",
                (str(index),),
            )
        create_database_checkpoint(db_path)

    points = [point for point in list_recovery_points(settings.state) if point["kind"] == "checkpoint"]

    assert len(points) == 5
    assert all(point["integrity"] == "ok" for point in points)


def test_recovery_checkpoint_api_records_audit_event(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    init_db(settings)
    client = TestClient(app_module.app)

    response = client.post("/api/recovery/checkpoint")

    assert response.status_code == 200
    point = response.json()
    assert point["integrity"] == "ok"

    listed = client.get("/api/recovery")
    assert listed.status_code == 200
    assert any(item["name"] == point["name"] for item in listed.json())

    audit = client.get("/api/audit?limit=20")
    assert audit.status_code == 200
    event = next(item for item in audit.json() if item["event"] == "recovery-checkpoint")
    assert event["payload"]["name"] == point["name"]


def test_corrupt_database_is_not_saved_as_verified_checkpoint(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    db_path = settings.state / "docpilot.sqlite3"
    db_path.write_bytes(b"not-a-sqlite-database")
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    response = client.post("/api/recovery/checkpoint")

    assert response.status_code == 409
    recovery_dir = settings.state / "recovery"
    assert not recovery_dir.exists() or list(recovery_dir.glob("*.sqlite3")) == []
