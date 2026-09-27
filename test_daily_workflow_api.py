import importlib
import io
import zipfile
from datetime import date, timedelta

from fastapi.testclient import TestClient

from docpilot.config import get_settings


def test_daily_workflow_through_public_api(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)

    deadline = date.today() + timedelta(days=5)
    document_date = date.today()
    invoice_text = (
        "ACME Services Sp. z o.o.\n"
        "Faktura VAT nr API/2026/77\n"
        f"Data: {document_date.strftime('%d.%m.%Y')}\n"
        f"Termin płatności: {deadline.strftime('%d.%m.%Y')}\n"
        "Do zapłaty 249,99 PLN\n"
    ).encode("utf-8")

    with TestClient(app_module.app) as client:
        analyzed = client.post(
            "/api/analyze",
            files={"upload": ("acme-invoice.txt", invoice_text, "text/plain")},
        )
        assert analyzed.status_code == 200
        invoice = analyzed.json()
        invoice_id = invoice["id"]

        patched = client.patch(
            f"/api/documents/{invoice_id}",
            json={
                "case_name": "ACME 2026",
                "action_required": "to-pay",
                "profile": "Home",
            },
        )
        assert patched.status_code == 200
        assert patched.json()["case_name"] == "ACME 2026"

        dashboard = client.get("/api/dashboard")
        assert dashboard.status_code == 200
        data = dashboard.json()
        assert data["documents"] == 1
        assert data["deadline_count"] >= 1
        assert any(item["id"] == invoice_id for item in data["deadlines"])

        search = client.get("/api/search", params={"q": "ACME faktura"})
        assert search.status_code == 200
        results = search.json()
        assert results
        assert results[0]["id"] == invoice_id

        qa = client.post(
            "/api/qa",
            json={"question": "jaki jest najbliższy termin ACME faktura"},
        )
        assert qa.status_code == 200
        answer = qa.json()
        assert deadline.isoformat() in answer["answer"]
        assert any(source["id"] == invoice_id for source in answer["sources"])

        cases = client.get("/api/cases")
        assert cases.status_code == 200
        acme_case = next(item for item in cases.json() if item["name"] == "ACME 2026")
        assert len(acme_case["documents"]) == 1
        assert acme_case["timeline"][0]["id"] == invoice_id
        assert acme_case["timeline"][0]["deadline"] == deadline.isoformat()
        assert acme_case["timeline"][0]["action"] == "to-pay"

        unclear = client.post(
            "/api/analyze",
            files={
                "upload": (
                    "urzad-letter.txt",
                    (
                        "Urząd Testowy\n"
                        "Pismo urzędowe\n"
                        "Prosimy o odpowiedź do dnia wskazanego w piśmie."
                    ).encode("utf-8"),
                    "text/plain",
                )
            },
        )
        assert unclear.status_code == 200
        unclear_id = unclear.json()["id"]

        review = client.get("/api/review")
        assert review.status_code == 200
        reviewed = next(item for item in review.json() if item["id"] == unclear_id)
        codes = {reason["code"] for reason in reviewed["reasons"]}
        assert "uncertain-deadline" in codes

        calendar = client.get("/api/export/calendar")
        assert calendar.status_code == 200
        calendar_text = calendar.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in calendar_text
        assert deadline.strftime("%Y%m%d") in calendar_text
        assert "acme-invoice.txt" in calendar_text

        backup = client.get("/api/export/backup")
        assert backup.status_code == 200
        with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
            assert "documents.json" in archive.namelist()
            assert "README.txt" in archive.namelist()

        full_backup = client.get("/api/export/backup-full")
        assert full_backup.status_code == 200
        with zipfile.ZipFile(io.BytesIO(full_backup.content)) as archive:
            names = archive.namelist()
            assert "documents.json" in names
            assert "manifest.json" in names
            assert any(name.startswith("source-files/") for name in names)

    with TestClient(app_module.app) as restarted_client:
        documents = restarted_client.get("/api/documents")
        assert documents.status_code == 200
        persisted_ids = {item["id"] for item in documents.json()}
        assert {invoice_id, unclear_id}.issubset(persisted_ids)
