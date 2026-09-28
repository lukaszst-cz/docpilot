import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import list_documents


def test_import_apply_and_undo_keep_index_in_sync(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)

    client = TestClient(app_module.app)
    content = (
        b"ACME Sp. z o.o.\n"
        b"Faktura VAT nr FV/31/2026\n"
        b"Data: 20.09.2026\n"
        b"Termin platnosci: 30.09.2026\n"
        b"Do zaplaty 199,99 PLN\n"
    )

    analyzed = client.post(
        "/api/analyze",
        files={"upload": ("invoice.txt", content, "text/plain")},
    )
    assert analyzed.status_code == 200
    source_path = Path(analyzed.json()["source_path"])
    assert source_path.exists()

    initial_docs = list_documents(temp_settings)
    assert len(initial_docs) == 1
    assert Path(initial_docs[0]["path"]) == source_path

    applied = client.post(
        "/api/apply",
        json={
            "source_path": str(source_path),
            "category": "Finance/Invoices",
            "filename": "2026-09-20-acme-invoice.txt",
            "mode": "organize",
            "profile": "Home",
            "case_name": None,
            "action_required": "to-pay",
            "smart_structure": False,
        },
    )
    assert applied.status_code == 200
    change = applied.json()
    destination = Path(change["destination"])
    assert destination.exists()
    assert not source_path.exists()

    moved_docs = list_documents(temp_settings)
    assert len(moved_docs) == 1
    assert Path(moved_docs[0]["path"]) == destination

    undone = client.post(f"/api/undo/{change['id']}")
    assert undone.status_code == 200
    restored = Path(undone.json()["restored_to"])
    assert restored.exists()
    assert not destination.exists()
    assert restored.read_bytes() == content

    restored_docs = list_documents(temp_settings)
    assert len(restored_docs) == 1
    assert Path(restored_docs[0]["path"]) == restored
    assert Path(restored_docs[0]["path"]).exists()


def test_api_organize_uses_selected_profile_space(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    analyzed = client.post(
        "/api/analyze",
        files={"upload": ("company.txt", b"Company contract document", "text/plain")},
    )
    assert analyzed.status_code == 200

    applied = client.post(
        "/api/apply",
        json={
            "source_path": analyzed.json()["source_path"],
            "category": "Contracts",
            "filename": "company-contract.txt",
            "mode": "organize",
            "profile": "Company",
            "case_name": None,
            "action_required": None,
            "smart_structure": False,
        },
    )
    assert applied.status_code == 200

    destination = Path(applied.json()["destination"])
    assert destination.parent == (
        temp_settings.archive / "Profiles" / "Company" / "Contracts"
    ).resolve()
