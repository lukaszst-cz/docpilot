import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import list_documents


def test_safe_demo_indexes_only_a_bundled_copy(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)

    client = TestClient(app_module.app)
    response = client.post("/api/demo")

    assert response.status_code == 200
    data = response.json()
    assert data["source_mode"] == "demo"

    demo_path = Path(data["source_path"])
    assert demo_path.exists()
    assert demo_path.parent == temp_settings.inbox
    assert demo_path.name.startswith("DocPilot-demo-invoice")

    docs = list_documents(temp_settings)
    assert len(docs) == 1
    assert Path(docs[0]["path"]) == demo_path
