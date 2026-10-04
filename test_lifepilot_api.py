import importlib
import io
import json
import zipfile

from fastapi.testclient import TestClient

from docpilot.config import get_settings


def test_lifepilot_api_exposes_next_action_proofpack_calendar_and_about(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    analyzed = client.post(
        "/api/analyze",
        files={
            "upload": (
                "invoice.txt",
                b"ACME\nFaktura VAT\nData: 01.10.2026\nTermin platnosci: 06.10.2026\nDo zaplaty 199,99 PLN\n",
                "text/plain",
            )
        },
    )
    assert analyzed.status_code == 200
    payload = analyzed.json()
    doc_id = payload["id"]
    assert payload["lifepilot"]["next_action"]["title"]

    view = client.get(f"/api/lifepilot/{doc_id}")
    assert view.status_code == 200
    assert "next_action" in view.json()
    assert "proof_pack" in view.json()

    preview = client.get(f"/api/lifepilot/{doc_id}/proofpack-preview")
    assert preview.status_code == 200
    assert preview.json()["privacy"]["uploads_anything"] is False
    assert any(item["name"] == "manifest.json" for item in preview.json()["files"])

    queue_before = client.get("/api/lifepilot/queue").json()
    assert any(item["id"] == doc_id for item in queue_before)
    marked = client.post(f"/api/lifepilot/{doc_id}/done")
    assert marked.status_code == 200
    assert marked.json()["done_at"]
    assert all(item["id"] != doc_id for item in client.get("/api/lifepilot/queue").json())
    with_done = client.get("/api/lifepilot/queue?include_done=true").json()
    assert any(item["id"] == doc_id and item["done"] is True and item["done_at"] for item in with_done)
    reopened = client.post(f"/api/lifepilot/{doc_id}/reopen")
    assert reopened.status_code == 200
    assert any(item["id"] == doc_id for item in client.get("/api/lifepilot/queue").json())

    proof = client.get(f"/api/lifepilot/{doc_id}/proofpack")
    assert proof.status_code == 200
    assert proof.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(proof.content)) as archive:
        assert "manifest.json" in archive.namelist()
        assert "SHA256SUMS.txt" in archive.namelist()
        assert any(name.startswith("original/") for name in archive.namelist())

    calendar = client.get(f"/api/lifepilot/{doc_id}/calendar")
    assert calendar.status_code == 200
    assert calendar.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in calendar.text

    about = client.get("/lifepilot")
    assert about.status_code == 200
    assert "Dokument" in about.text
    assert "ProofPack" in about.text


def test_calendar_export_accepts_warranty_date(monkeypatch, tmp_path):
    from docpilot.exporters import ics_for_documents

    content = ics_for_documents([
        {
            "id": 99,
            "source_name": "warranty.pdf",
            "path": "warranty.pdf",
            "action_required": "to-renew",
            "metadata": {"warranty_until": "2026-12-31"},
        }
    ])
    assert "DTSTART;VALUE=DATE:20261231" in content
    assert "BEGIN:VEVENT" in content


def test_verified_corrections_recompute_lifepilot_and_survive_apply(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    analyzed = client.post(
        "/api/analyze",
        files={"upload": ("letter.txt", b"Nieczytelny dokument do sprawdzenia", "text/plain")},
    )
    assert analyzed.status_code == 200
    original = analyzed.json()
    assert original["metadata"]["confidence"] < 0.65

    corrected = client.patch(
        f"/api/lifepilot/{original['id']}/fields",
        json={
            "document_type": "official-letter",
            "issuer": "Urzad Testowy",
            "amount": None,
            "currency": None,
            "document_date": "2026-10-04",
            "deadline": "2026-10-08",
            "warranty_until": None,
            "case_name": "Sprawa testowa",
            "action_required": "to-reply",
        },
    )
    assert corrected.status_code == 200
    payload = corrected.json()
    assert payload["metadata"]["manual_verified"] is True
    assert payload["metadata"]["deadline"] == "2026-10-08"
    assert payload["case_name"] == "Sprawa testowa"
    assert payload["lifepilot"]["next_action"]["title"] == "Przygotuj odpowiedź"

    applied = client.post(
        "/api/apply",
        json={
            "source_path": original["source_path"],
            "category": "Official",
            "filename": "verified-letter.txt",
            "mode": "organize",
            "profile": "Home",
            "case_name": "Sprawa testowa",
            "action_required": "to-reply",
            "smart_structure": False,
            "metadata_overrides": {
                "document_type": payload["metadata"]["document_type"],
                "issuer": payload["metadata"]["issuer"],
                "amount": payload["metadata"]["amount"],
                "currency": payload["metadata"]["currency"],
                "document_date": payload["metadata"]["document_date"],
                "deadline": payload["metadata"]["deadline"],
                "warranty_until": payload["metadata"]["warranty_until"],
            },
        },
    )
    assert applied.status_code == 200
    moved_id = applied.json()["document_id"]
    moved = client.get(f"/api/lifepilot/{moved_id}")
    assert moved.status_code == 200
    assert moved.json()["next_action"]["title"] == "Przygotuj odpowiedź"

    document = client.get("/api/documents").json()[0]
    assert document["metadata"]["manual_verified"] is True
    assert document["metadata"]["deadline"] == "2026-10-08"


def test_case_summary_preview_and_markdown_export_are_private(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    ids = []
    for name, content, day in [
        ("first.txt", b"ACME Faktura VAT\nData: 01.10.2026\nTermin platnosci: 06.10.2026\n199,99 PLN", "2026-10-01"),
        ("second.txt", b"Urzad Testowy\nWezwanie\nData: 03.10.2026\nOdpowiedz do 10.10.2026", "2026-10-03"),
    ]:
        analyzed = client.post("/api/analyze", files={"upload": (name, content, "text/plain")})
        assert analyzed.status_code == 200
        doc_id = analyzed.json()["id"]
        ids.append(doc_id)
        corrected = client.patch(
            f"/api/lifepilot/{doc_id}/fields",
            json={"document_date": day, "case_name": "Sprawa eksportowa"},
        )
        assert corrected.status_code == 200

    summary = client.get("/api/lifepilot/case-summary", params={"case_name": "Sprawa eksportowa"})
    assert summary.status_code == 200
    data = summary.json()
    assert data["document_count"] == 2
    assert data["privacy"]["includes_extracted_text"] is False
    assert data["privacy"]["includes_local_paths"] is False
    assert all(item.get("sha256") for item in data["timeline"])

    exported = client.get("/api/lifepilot/case-summary/export", params={"case_name": "Sprawa eksportowa"})
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/markdown")
    assert "first.txt" in exported.text
    assert "second.txt" in exported.text
    assert str(tmp_path) not in exported.text
    assert "Nieczytelny dokument" not in exported.text


def test_legacy_handled_signature_remains_compatible(monkeypatch, tmp_path):
    from docpilot.db import set_setting
    from docpilot.lifepilot import legacy_attention_signature

    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    analyzed = client.post(
        "/api/analyze",
        files={"upload": ("legacy.txt", b"ACME Faktura VAT\nTermin platnosci: 06.10.2026\n199,99 PLN", "text/plain")},
    )
    assert analyzed.status_code == 200
    doc_id = analyzed.json()["id"]
    document = next(item for item in client.get("/api/documents").json() if item["id"] == doc_id)
    set_setting(
        temp_settings,
        "lifepilot.done",
        json.dumps({str(doc_id): legacy_attention_signature(document)}),
    )

    queue = client.get("/api/lifepilot/queue?include_done=true").json()
    legacy = next(item for item in queue if item["id"] == doc_id)
    assert legacy["done"] is True
    assert legacy["done_at"] is None
