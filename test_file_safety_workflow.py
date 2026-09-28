import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.storage import list_changes


def _client(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    return app_module, temp_settings, TestClient(app_module.app)


def test_select_local_only_analyzes_original(monkeypatch, tmp_path):
    app_module, settings, client = _client(monkeypatch, tmp_path)

    source = tmp_path / "user-files" / "source.txt"
    source.parent.mkdir()
    original = b"Important source document\nInvoice 100 PLN\n"
    source.write_bytes(original)
    before_mtime = source.stat().st_mtime_ns

    monkeypatch.setattr(app_module, "_pick_file_windows", lambda *args, **kwargs: str(source))
    monkeypatch.setattr(app_module, "_pick_file_fallback", lambda *args, **kwargs: str(source))

    response = client.post("/api/select-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "original"
    assert Path(payload["source_path"]) == source.resolve()
    assert source.exists()
    assert source.read_bytes() == original
    assert source.stat().st_mtime_ns == before_mtime
    assert list_changes(settings) == []


def test_original_rename_is_recorded_in_undo_history(monkeypatch, tmp_path):
    _app_module, settings, client = _client(monkeypatch, tmp_path)

    source = tmp_path / "user-files" / "old-name.txt"
    source.parent.mkdir()
    source.write_text("invoice 123 PLN", encoding="utf-8")

    response = client.post(
        "/api/apply",
        json={
            "source_path": str(source),
            "category": "Documents",
            "filename": "new-name.txt",
            "mode": "rename",
            "profile": "Home",
            "case_name": None,
            "action_required": None,
            "smart_structure": False,
        },
    )

    assert response.status_code == 200
    change = response.json()
    assert change["action"] == "rename"
    assert change["verified"] is True

    history = client.get("/api/changes")
    assert history.status_code == 200
    item = next(entry for entry in history.json() if entry["id"] == change["id"])
    assert item["action"] == "rename"
    assert item["source"] == str(source.resolve())
    assert Path(item["destination"]).name == "new-name.txt"
    assert item["verified"] is True


def test_original_move_and_rename_is_recorded_in_undo_history(monkeypatch, tmp_path):
    _app_module, settings, client = _client(monkeypatch, tmp_path)

    source = tmp_path / "user-files" / "scan.txt"
    source.parent.mkdir()
    source.write_text("contract text", encoding="utf-8")

    response = client.post(
        "/api/apply",
        json={
            "source_path": str(source),
            "category": "Legal/Contracts",
            "filename": "2026-contract.txt",
            "mode": "organize",
            "profile": "Home",
            "case_name": None,
            "action_required": None,
            "smart_structure": False,
        },
    )

    assert response.status_code == 200
    change = response.json()
    assert change["action"] == "move"
    assert change["verified"] is True

    destination = Path(change["destination"])
    assert destination.exists()
    assert destination.name == "2026-contract.txt"
    assert destination.parent == (settings.archive / "Legal" / "Contracts").resolve()

    history = client.get("/api/changes")
    assert history.status_code == 200
    item = next(entry for entry in history.json() if entry["id"] == change["id"])
    assert item["action"] == "move"
    assert item["source"] == str(source.resolve())
    assert Path(item["destination"]) == destination
    assert item["verified"] is True
