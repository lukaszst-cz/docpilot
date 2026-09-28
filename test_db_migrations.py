from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import init_db
from docpilot.db_maintenance import CURRENT_SCHEMA_VERSION, create_database_checkpoint, database_health


LEGACY_SCHEMA = """
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    extracted_text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL,
    category TEXT NOT NULL,
    suggested_filename TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    profile TEXT NOT NULL DEFAULT 'Home',
    case_name TEXT,
    action_required TEXT,
    health_score INTEGER NOT NULL DEFAULT 100,
    health_json TEXT NOT NULL DEFAULT '[]',
    simhash TEXT,
    indexed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    target_category TEXT,
    target_profile TEXT,
    target_tags_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE custom_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    keywords_json TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Documents'
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def _legacy_database(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(LEGACY_SCHEMA)
        conn.execute(
            """
            INSERT INTO documents(
                path,source_name,sha256,size_bytes,extracted_text,metadata_json,category,
                suggested_filename,tags_json,profile,case_name,action_required,health_score,
                health_json,simhash,indexed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "/legacy/invoice.txt",
                "invoice.txt",
                "legacy-sha",
                123,
                "legacy invoice",
                '{"document_type":"invoice"}',
                "Finance/Invoices",
                "invoice.txt",
                "[]",
                "Home",
                "Legacy Case",
                "to-pay",
                100,
                "[]",
                None,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )


def test_unversioned_legacy_database_is_preserved_and_backed_up(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = settings.state / "docpilot.sqlite3"
    _legacy_database(db_path)

    init_db(settings)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT source_name FROM documents").fetchone()[0] == "invoice.txt"
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "integration_runs" in tables
        assert "integration_links" in tables

    backups = list((settings.state / "migration-backups").glob("*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as legacy:
        assert legacy.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        tables = {row[0] for row in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "integration_runs" not in tables


def test_reopening_current_schema_does_not_create_another_migration_backup(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = settings.state / "docpilot.sqlite3"
    _legacy_database(db_path)

    init_db(settings)
    init_db(settings)
    init_db(settings)

    backups = list((settings.state / "migration-backups").glob("*.sqlite3"))
    assert len(backups) == 1


def test_newer_schema_is_rejected_instead_of_modified(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = settings.state / "docpilot.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version=999")

    with pytest.raises(RuntimeError, match="newer than this DocPilot build supports"):
        init_db(settings)


def test_database_health_reports_integrity_and_schema(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)

    health = database_health(db_path)

    assert health["status"] == "ok"
    assert health["integrity"] == "ok"
    assert health["schema_version"] == CURRENT_SCHEMA_VERSION
    assert health["supported_schema_version"] == CURRENT_SCHEMA_VERSION
    assert health["journal_mode"].lower() == "wal"


def test_diagnostics_reports_database_compatibility(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    init_db(settings)

    client = TestClient(app_module.app)
    response = client.get("/api/diagnostics")

    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "ok"
    assert data["database_integrity"] == "ok"
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert data["supported_schema_version"] == CURRENT_SCHEMA_VERSION
    assert data["migration_backups"] == 0


def test_diagnostics_recommends_checkpoint_when_database_is_healthy_but_unprotected(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    init_db(settings)

    client = TestClient(app_module.app)
    data = client.get("/api/diagnostics").json()

    assert data["database_integrity"] == "ok"
    assert data["verified_recovery_points"] == 0
    assert data["recovery_status"] == "checkpoint-recommended"
    assert "Create a checkpoint" in data["recovery_message"]
    assert data["latest_recovery_point"] is None


def test_diagnostics_reports_ready_after_verified_checkpoint(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    db_path = init_db(settings)
    checkpoint = create_database_checkpoint(db_path)

    client = TestClient(app_module.app)
    data = client.get("/api/diagnostics").json()

    assert data["database_integrity"] == "ok"
    assert data["verified_recovery_points"] == 1
    assert data["recovery_status"] == "ready"
    assert data["latest_recovery_point"] == checkpoint["modified_at"]
    assert "verified recovery point" in data["recovery_message"]


def test_safe_diagnostic_report_includes_recovery_readiness(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    init_db(settings)

    client = TestClient(app_module.app)
    response = client.get("/api/diagnostics/report")

    assert response.status_code == 200
    text = response.text
    assert "Recovery readiness: checkpoint-recommended" in text
    assert "Verified recovery points: 0" in text
    assert "Latest recovery point: none" in text
