from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import docpilot
from docpilot.config import get_settings
from docpilot.db import connect, get_setting, init_db
from docpilot.db_maintenance import create_database_checkpoint, database_health


def _corrupt_active_database(settings) -> tuple[Path, str]:
    db_path = init_db(settings)
    with connect(settings) as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('recovery-marker','good-state')")
    checkpoint = create_database_checkpoint(db_path)

    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    db_path.write_bytes(b"corrupt-active-database")
    return db_path, checkpoint["name"]


def test_corrupt_database_starts_recovery_mode_and_restores_without_restart(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    db_path, checkpoint_name = _corrupt_active_database(settings)

    bootstrap_error = app_module._bootstrap_database(settings)
    assert bootstrap_error

    monkeypatch.setattr(app_module, "settings", settings)
    monkeypatch.setattr(app_module, "DATABASE_BOOTSTRAP_ERROR", bootstrap_error)

    with TestClient(app_module.app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "degraded"
        assert health.json()["database_ready"] is False

        diagnostics = client.get("/api/diagnostics")
        assert diagnostics.status_code == 200
        data = diagnostics.json()
        assert data["database_startup"] == "degraded"
        assert data["database"] == "attention"
        assert data["database_integrity"] == "unreadable"
        assert data["documents"] == 0
        checks = {item["code"]: item for item in data["assessment"]["checks"]}
        assert checks["database-startup"]["status"] == "error"
        assert checks["schema"]["status"] == "info"
        assert data["assessment"]["status"] == "error"

        blocked = client.get("/api/documents")
        assert blocked.status_code == 503
        assert "recovery mode" in blocked.json()["detail"].lower()

        recovery = client.get("/api/recovery")
        assert recovery.status_code == 200
        assert any(
            item["name"] == checkpoint_name and item["integrity"] == "ok"
            for item in recovery.json()
        )

        restored = client.post(
            "/api/recovery/restore",
            json={"name": checkpoint_name, "confirm": "RESTORE"},
        )
        assert restored.status_code == 200
        assert restored.json()["restored_from"]["name"] == checkpoint_name
        assert restored.json()["pre_restore_backup"]["kind"] == "pre-restore-corrupt"

        healthy = client.get("/api/health")
        assert healthy.status_code == 200
        assert healthy.json()["status"] == "ok"
        assert healthy.json()["database_ready"] is True

        after = client.get("/api/diagnostics")
        assert after.status_code == 200
        assert after.json()["database_startup"] == "ok"
        assert after.json()["database_integrity"] == "ok"
        assert after.json()["upgrade_recovery"]["status"] == "restored"

        documents = client.get("/api/documents")
        assert documents.status_code == 200

    assert get_setting(settings, "recovery-marker") == "good-state"
    assert database_health(db_path)["integrity"] == "ok"


def test_future_schema_starts_degraded_and_blocks_normal_document_work(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version=999")

    bootstrap_error = app_module._bootstrap_database(settings)
    assert bootstrap_error
    assert "newer" in bootstrap_error.lower()

    monkeypatch.setattr(app_module, "settings", settings)
    monkeypatch.setattr(app_module, "DATABASE_BOOTSTRAP_ERROR", bootstrap_error)

    with TestClient(app_module.app) as client:
        assert client.get("/api/health").json()["status"] == "degraded"

        diagnostics = client.get("/api/diagnostics")
        assert diagnostics.status_code == 200
        data = diagnostics.json()
        assert data["database_startup"] == "degraded"
        assert data["database_integrity"] == "ok"
        assert data["schema_version"] == 999
        checks = {item["code"]: item for item in data["assessment"]["checks"]}
        assert checks["schema"]["status"] == "error"

        assert client.get("/api/documents").status_code == 503


def test_safe_diagnostic_report_omits_local_paths_and_document_contents(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "Private User Folder")
    init_db(settings)
    private_document = tmp_path / "Private User Folder" / "secret-contract.txt"
    private_document.write_text("SECRET CONTRACT CONTENT 12345", encoding="utf-8")

    with connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO documents(
                path,source_name,sha256,size_bytes,extracted_text,metadata_json,category,
                suggested_filename,tags_json,profile,case_name,action_required,health_score,
                health_json,simhash,indexed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(private_document),
                private_document.name,
                "secret-sha",
                private_document.stat().st_size,
                "SECRET CONTRACT CONTENT 12345",
                '{"document_type":"contract","confidence":0.9}',
                "Contracts",
                private_document.name,
                "[]",
                "Home",
                "Private Case",
                None,
                100,
                "[]",
                None,
                "2026-09-28T00:00:00+00:00",
                "2026-09-28T00:00:00+00:00",
            ),
        )

    monkeypatch.setattr(app_module, "settings", settings)
    monkeypatch.setattr(app_module, "DATABASE_BOOTSTRAP_ERROR", None)

    with TestClient(app_module.app) as client:
        report = client.get("/api/diagnostics/report")
        assert report.status_code == 200
        body = report.text

    assert "SECRET CONTRACT CONTENT 12345" not in body
    assert "secret-contract.txt" not in body
    assert "Private User Folder" not in body
    assert str(settings.root) not in body


def test_desktop_wait_accepts_recovery_mode(monkeypatch):
    import docpilot.desktop as desktop

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"status": "degraded", "version": docpilot.__version__}).encode("utf-8")

    monkeypatch.setattr(desktop.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    assert desktop._wait_until_ready(timeout=0.1) is True
