from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import SCHEMA, connect, init_db
from docpilot.db_maintenance import create_database_checkpoint, list_recovery_points, restore_database_from_point


def _set_marker(settings, value: str) -> None:
    with connect(settings) as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('restore-marker',?)", (value,))


def _get_marker(settings) -> str:
    with connect(settings) as conn:
        return conn.execute("SELECT value FROM settings WHERE key='restore-marker'").fetchone()[0]


def test_restore_reverts_database_and_keeps_pre_restore_backup(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    _set_marker(settings, "before")
    checkpoint = create_database_checkpoint(db_path)

    _set_marker(settings, "after")
    result = restore_database_from_point(db_path, checkpoint["name"], SCHEMA)

    assert _get_marker(settings) == "before"
    assert result["restored_from"]["name"] == checkpoint["name"]
    safety = result["pre_restore_backup"]
    assert safety is not None
    assert safety["kind"] == "pre-restore"
    assert safety["integrity"] == "ok"

    safety_path = settings.state / "recovery" / safety["name"]
    with sqlite3.connect(safety_path) as conn:
        assert conn.execute(
            "SELECT value FROM settings WHERE key='restore-marker'"
        ).fetchone()[0] == "after"

    points = list_recovery_points(settings.state)
    assert any(item["name"] == safety["name"] and item["kind"] == "pre-restore" for item in points)


def test_restore_rejects_path_traversal(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)

    try:
        restore_database_from_point(db_path, "../docpilot.sqlite3", SCHEMA)
    except ValueError as exc:
        assert "Invalid recovery point name" in str(exc)
    else:
        raise AssertionError("path traversal recovery point was accepted")


def test_restore_can_recover_from_corrupt_active_database(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    _set_marker(settings, "good")
    checkpoint = create_database_checkpoint(db_path)

    db_path.write_bytes(b"corrupt-current-database")

    result = restore_database_from_point(db_path, checkpoint["name"], SCHEMA)

    assert _get_marker(settings) == "good"
    safety = result["pre_restore_backup"]
    assert safety["kind"] == "pre-restore-corrupt"
    assert safety["integrity"] == "unreadable"
    assert (settings.state / "recovery" / safety["name"]).read_bytes() == b"corrupt-current-database"


def test_restore_api_requires_explicit_confirmation(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    monkeypatch.setattr(app_module, "settings", settings)
    checkpoint = create_database_checkpoint(db_path)
    client = TestClient(app_module.app)

    missing = client.post("/api/recovery/restore", json={"name": checkpoint["name"]})
    assert missing.status_code == 400

    wrong = client.post(
        "/api/recovery/restore",
        json={"name": checkpoint["name"], "confirm": "restore"},
    )
    assert wrong.status_code == 400


def test_restore_api_restores_and_audits(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    monkeypatch.setattr(app_module, "settings", settings)
    _set_marker(settings, "checkpoint-state")
    checkpoint = create_database_checkpoint(db_path)
    _set_marker(settings, "changed-state")
    client = TestClient(app_module.app)

    response = client.post(
        "/api/recovery/restore",
        json={"name": checkpoint["name"], "confirm": "RESTORE"},
    )

    assert response.status_code == 200
    assert _get_marker(settings) == "checkpoint-state"
    payload = response.json()
    assert payload["restored_from"]["name"] == checkpoint["name"]
    assert payload["pre_restore_backup"]["integrity"] == "ok"

    audit = client.get("/api/audit?limit=50")
    assert audit.status_code == 200
    event = next(item for item in audit.json() if item["event"] == "recovery-restore")
    assert event["payload"]["restored_from"] == checkpoint["name"]
