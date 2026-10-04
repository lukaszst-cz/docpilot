import importlib
import io
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
