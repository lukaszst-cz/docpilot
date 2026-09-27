import importlib

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import get_setting


def test_first_run_setup_status_can_be_completed(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    monkeypatch.setattr(
        app_module,
        "_ocr_runtime_status",
        lambda: {"ready": True, "version": "test-ocr"},
    )

    client = TestClient(app_module.app)
    initial = client.get("/api/setup/status")
    assert initial.status_code == 200
    data = initial.json()
    assert data["complete"] is False
    assert data["has_documents"] is False
    assert data["ocr"] == {"ready": True, "version": "test-ocr"}
    assert data["demo_ready"] is True
    assert data["data_root"] == str(temp_settings.root)
    assert data["recommended_free_space_gb"] == 2

    completed = client.post("/api/setup", json={"complete": True})
    assert completed.status_code == 200
    assert completed.json()["complete"] is True
    assert get_setting(temp_settings, "onboarding_complete") == "1"

    reopened = client.post("/api/setup", json={"complete": False})
    assert reopened.status_code == 200
    assert reopened.json()["complete"] is False
