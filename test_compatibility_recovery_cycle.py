from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import SCHEMA, connect, init_db
from docpilot.db_maintenance import (
    CURRENT_SCHEMA_VERSION,
    create_database_checkpoint,
    database_health,
    restore_database_from_point,
)


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


def _create_legacy_database(path) -> None:
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
                "/legacy/acme-invoice.txt",
                "acme-invoice.txt",
                "legacy-sha",
                321,
                "ACME legacy invoice flooding claim",
                '{"document_type":"invoice","issuer":"ACME","confidence":0.95}',
                "Finance/Invoices",
                "acme-invoice.txt",
                "[]",
                "Home",
                "Legacy ACME",
                "to-pay",
                100,
                "[]",
                None,
                "2025-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
            ),
        )
        conn.execute("INSERT INTO settings(key,value) VALUES('compatibility-marker','legacy')")
        conn.execute(
            """
            INSERT INTO rules(name,condition_json,target_category,target_profile,target_tags_json,enabled)
            VALUES('Legacy invoices','{"document_type":"invoice"}','Finance/Invoices','Home','[]',1)
            """
        )


def _marker(settings) -> str:
    with connect(settings) as conn:
        return conn.execute(
            "SELECT value FROM settings WHERE key='compatibility-marker'"
        ).fetchone()[0]


def test_legacy_upgrade_checkpoint_restore_and_reopen_cycle(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    db_path = settings.state / "docpilot.sqlite3"
    _create_legacy_database(db_path)

    init_db(settings)
    health = database_health(db_path)
    assert health["integrity"] == "ok"
    assert health["schema_version"] == CURRENT_SCHEMA_VERSION

    migration_backups = list((settings.state / "migration-backups").glob("*.sqlite3"))
    assert len(migration_backups) == 1

    checkpoint = create_database_checkpoint(db_path)

    with connect(settings) as conn:
        conn.execute(
            "UPDATE settings SET value='changed-after-checkpoint' WHERE key='compatibility-marker'"
        )
        conn.execute(
            "UPDATE documents SET source_name='changed-name.txt', extracted_text='changed text' WHERE id=1"
        )

    restored = restore_database_from_point(db_path, checkpoint["name"], SCHEMA)
    assert restored["database"]["integrity"] == "ok"
    assert restored["database"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert restored["pre_restore_backup"]["integrity"] == "ok"
    assert _marker(settings) == "legacy"

    # Reopening after restore must remain idempotent and must not create another migration backup.
    init_db(settings)
    assert len(list((settings.state / "migration-backups").glob("*.sqlite3"))) == 1

    with connect(settings) as conn:
        row = conn.execute("SELECT source_name, extracted_text FROM documents WHERE id=1").fetchone()
        assert row["source_name"] == "acme-invoice.txt"
        assert row["extracted_text"] == "ACME legacy invoice flooding claim"
        assert conn.execute("SELECT COUNT(*) FROM integration_runs").fetchone()[0] == 0

    safety_path = settings.state / "recovery" / restored["pre_restore_backup"]["name"]
    with sqlite3.connect(safety_path) as conn:
        assert conn.execute(
            "SELECT value FROM settings WHERE key='compatibility-marker'"
        ).fetchone()[0] == "changed-after-checkpoint"

    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["documents"] == 1

    search = client.get("/api/search", params={"q": "legacy flooding"})
    assert search.status_code == 200
    assert search.json()
    assert search.json()[0]["source_name"] == "acme-invoice.txt"

    rules = client.get("/api/rules")
    assert rules.status_code == 200
    assert rules.json()[0]["name"] == "Legacy invoices"


def test_corrupt_recovery_point_is_rejected_without_touching_active_database(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    with connect(settings) as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES('compatibility-marker','active')")

    checkpoint = create_database_checkpoint(db_path)
    checkpoint_path = settings.state / "recovery" / checkpoint["name"]
    checkpoint_path.write_bytes(b"not-a-sqlite-checkpoint")

    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        restore_database_from_point(db_path, checkpoint["name"], SCHEMA)

    assert _marker(settings) == "active"
    assert database_health(db_path)["integrity"] == "ok"


def test_future_schema_recovery_point_is_rejected_without_touching_active_database(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    with connect(settings) as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES('compatibility-marker','active')")

    checkpoint = create_database_checkpoint(db_path)
    checkpoint_path = settings.state / "recovery" / checkpoint["name"]
    with sqlite3.connect(checkpoint_path) as conn:
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION + 50}")

    with pytest.raises(RuntimeError, match="newer than supported"):
        restore_database_from_point(db_path, checkpoint["name"], SCHEMA)

    assert _marker(settings) == "active"
    assert database_health(db_path)["integrity"] == "ok"
