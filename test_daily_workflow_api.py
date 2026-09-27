import importlib
import io
import zipfile

from fastapi.testclient import TestClient

from docpilot.config import get_settings


def _upload_text(client: TestClient, name: str, text: str) -> dict:
    response = client.post(
        "/api/analyze",
        files={"upload": (name, text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    return response.json()


def test_daily_local_workflow_through_api(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)

    with TestClient(app_module.app) as client:
        invoice = _upload_text(
            client,
            "energia.txt",
            "Energia Test Sp. z o.o.\n"
            "Faktura VAT nr EN/55/2026\n"
            "Data: 20.09.2026\n"
            "Termin płatności: 30.09.2026\n"
            "Do zapłaty 215,40 PLN\n"
            "energia elektryczna",
        )
        letter = _upload_text(
            client,
            "pismo-do-sprawdzenia.txt",
            "Prosimy o odpowiedź do dnia wskazanego w piśmie. "
            "Dokument wymaga ręcznego sprawdzenia.",
        )

        dashboard = client.get("/api/dashboard")
        assert dashboard.status_code == 200
        dash = dashboard.json()
        assert dash["documents"] == 2
        assert dash["deadline_count"] >= 1
        assert any(item["name"] == invoice["source_name"] for item in dash["deadlines"])

        review = client.get("/api/review")
        assert review.status_code == 200
        review_items = review.json()
        reviewed = next(item for item in review_items if item["name"] == letter["source_name"])
        review_codes = {reason["code"] for reason in reviewed["reasons"]}
        assert "low-confidence" in review_codes
        assert "uncertain-deadline" in review_codes

        search = client.get("/api/search", params={"q": "energia elektryczna"})
        assert search.status_code == 200
        results = search.json()
        assert results
        assert results[0]["source_name"] == invoice["source_name"]

        qa = client.post("/api/qa", json={"question": "jaki jest najbliższy termin energia"})
        assert qa.status_code == 200
        answer = qa.json()
        assert "2026-09-30" in answer["answer"]
        assert answer["sources"]
        assert answer["sources"][0]["name"] == invoice["source_name"]

        patched = client.patch(
            f"/api/documents/{invoice['id']}",
            json={"case_name": "Dom — energia"},
        )
        assert patched.status_code == 200
        assert patched.json()["case_name"] == "Dom — energia"

        cases = client.get("/api/cases")
        assert cases.status_code == 200
        case = next(item for item in cases.json() if item["name"] == "Dom — energia")
        assert any(item["id"] == invoice["id"] for item in case["timeline"])

        calendar = client.get("/api/export/calendar")
        assert calendar.status_code == 200
        calendar_text = calendar.text
        assert "BEGIN:VCALENDAR" in calendar_text
        assert "DTSTART;VALUE=DATE:20260930" in calendar_text
        assert invoice["source_name"] in calendar_text

        backup = client.get("/api/export/backup")
        assert backup.status_code == 200
        with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
            assert "documents.json" in archive.namelist()
            assert "state/docpilot.sqlite3" in archive.namelist()

        full_backup = client.get("/api/export/backup-full")
        assert full_backup.status_code == 200
        with zipfile.ZipFile(io.BytesIO(full_backup.content)) as archive:
            names = archive.namelist()
            assert "manifest.json" in names
            assert any(name.startswith("source-files/") for name in names)

    # A fresh TestClient simulates reopening the local app against the same data directory.
    with TestClient(app_module.app) as reopened:
        documents = reopened.get("/api/documents")
        assert documents.status_code == 200
        saved = documents.json()
        assert len(saved) == 2
        assert any(item["source_name"] == invoice["source_name"] for item in saved)
        assert any(item["case_name"] == "Dom — energia" for item in saved)
