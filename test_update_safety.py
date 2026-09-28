from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import get_setting, init_db, list_audit, set_setting
from docpilot.update_safety import (
    LAST_STARTED_VERSION_KEY,
    LAST_UPGRADE_CHECKPOINT_KEY,
    ensure_version_recovery,
)


def test_first_start_records_version_without_creating_upgrade_checkpoint(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    init_db(settings)

    result = ensure_version_recovery(settings, "4.0.0")

    assert result == {
        "status": "initialized",
        "previous_version": None,
        "current_version": "4.0.0",
        "checkpoint": None,
    }
    assert get_setting(settings, LAST_STARTED_VERSION_KEY) == "4.0.0"
    assert get_setting(settings, LAST_UPGRADE_CHECKPOINT_KEY) is None
    recovery_dir = settings.state / "recovery"
    assert not recovery_dir.exists() or list(recovery_dir.glob("*.sqlite3")) == []


def test_version_change_creates_one_verified_checkpoint_and_is_idempotent(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    db_path = init_db(settings)
    set_setting(settings, LAST_STARTED_VERSION_KEY, "3.0.0")
    set_setting(settings, "upgrade-marker", "before-update")

    result = ensure_version_recovery(settings, "4.0.0")

    assert result["status"] == "checkpointed"
    assert result["previous_version"] == "3.0.0"
    assert result["current_version"] == "4.0.0"
    checkpoint_name = result["checkpoint"]
    assert checkpoint_name
    assert get_setting(settings, LAST_STARTED_VERSION_KEY) == "4.0.0"
    assert get_setting(settings, LAST_UPGRADE_CHECKPOINT_KEY) == checkpoint_name

    checkpoint_path = settings.state / "recovery" / checkpoint_name
    assert checkpoint_path.exists()
    with sqlite3.connect(checkpoint_path) as checkpoint:
        assert checkpoint.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert checkpoint.execute(
            "SELECT value FROM settings WHERE key='upgrade-marker'"
        ).fetchone()[0] == "before-update"

    repeated = ensure_version_recovery(settings, "4.0.0")
    assert repeated["status"] == "current"
    assert repeated["checkpoint"] == checkpoint_name
    assert len(list((settings.state / "recovery").glob("docpilot-checkpoint-*.sqlite3"))) == 1
    assert db_path.exists()


def test_failed_upgrade_checkpoint_does_not_advance_recorded_version(monkeypatch, tmp_path):
    import docpilot.update_safety as update_safety

    settings = get_settings(tmp_path / "DocPilotData")
    init_db(settings)
    set_setting(settings, LAST_STARTED_VERSION_KEY, "3.0.0")

    def fail_checkpoint(_path):
        raise RuntimeError("simulated checkpoint failure")

    monkeypatch.setattr(update_safety, "create_database_checkpoint", fail_checkpoint)

    with pytest.raises(RuntimeError, match="simulated checkpoint failure"):
        ensure_version_recovery(settings, "4.0.0")

    assert get_setting(settings, LAST_STARTED_VERSION_KEY) == "3.0.0"
    assert get_setting(settings, LAST_UPGRADE_CHECKPOINT_KEY) is None


def test_lifespan_creates_upgrade_checkpoint_and_reports_it(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    init_db(settings)
    set_setting(settings, LAST_STARTED_VERSION_KEY, "3.0.0")
    set_setting(settings, "upgrade-marker", "safe-before-start")

    monkeypatch.setattr(app_module, "settings", settings)
    monkeypatch.setattr(app_module, "__version__", "4.0.0")

    with TestClient(app_module.app) as client:
        diagnostics = client.get("/api/diagnostics")
        assert diagnostics.status_code == 200
        recovery = diagnostics.json()["upgrade_recovery"]
        assert recovery["status"] == "checkpointed"
        assert recovery["previous_version"] == "3.0.0"
        assert recovery["current_version"] == "4.0.0"
        assert recovery["checkpoint"]

        safe = diagnostics.json()["safe_report"]
        assert safe["upgrade_recovery"]["status"] == "checkpointed"
        checks = {item["code"]: item for item in diagnostics.json()["assessment"]["checks"]}
        assert checks["upgrade-recovery"]["status"] == "ok"

    events = [item for item in list_audit(settings, limit=50) if item["event"] == "upgrade-recovery-checkpoint"]
    assert len(events) == 1
    assert events[0]["payload"]["previous_version"] == "3.0.0"
    assert events[0]["payload"]["current_version"] == "4.0.0"


def test_upgrade_checkpoint_failure_does_not_block_app_start(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    init_db(settings)
    set_setting(settings, LAST_STARTED_VERSION_KEY, "3.0.0")

    monkeypatch.setattr(app_module, "settings", settings)
    monkeypatch.setattr(app_module, "__version__", "4.0.0")

    def fail_upgrade(_settings, _version):
        raise RuntimeError("simulated startup checkpoint failure")

    monkeypatch.setattr(app_module, "ensure_version_recovery", fail_upgrade)

    with TestClient(app_module.app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200

        diagnostics = client.get("/api/diagnostics")
        assert diagnostics.status_code == 200
        assert diagnostics.json()["upgrade_recovery"]["status"] == "error"
        checks = {item["code"]: item for item in diagnostics.json()["assessment"]["checks"]}
        assert checks["upgrade-recovery"]["status"] == "warning"
        assert any("Recovery checkpoint" in item or "recovery checkpoint" in item.lower() for item in diagnostics.json()["assessment"]["recommendations"])

    assert get_setting(settings, LAST_STARTED_VERSION_KEY) == "3.0.0"
