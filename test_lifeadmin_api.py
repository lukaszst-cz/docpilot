import importlib

from fastapi.testclient import TestClient

from docpilot.config import get_settings


def test_lifeadmin_api_and_analysis_context(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    analyzed = client.post(
        "/api/analyze",
        files={
            "upload": (
                "auto-oc.txt",
                (
                    "Ubezpieczenie OC pojazdu\n"
                    "Polisa OC nr CAR/2026/1\n"
                    "Samochod VIN ABC123456789\n"
                    "Wazne do 20.10.2026\n"
                ).encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert analyzed.status_code == 200
    data = analyzed.json()
    assert data["metadata"]["life_area"] == "car"
    assert data["metadata"]["life_event"] == "ubezpieczenie"
    assert data["metadata"]["life_action"] == "Sprawdź lub odnów polisę"
    assert data["profile"] == "Vehicle"

    dashboard = client.get("/api/lifeadmin")
    assert dashboard.status_code == 200
    summary = dashboard.json()
    by_key = {item["key"]: item for item in summary["areas"]}
    assert by_key["car"]["count"] == 1
    assert summary["timeline"][0]["area"] == "car"


def test_lifepilot_manual_correction_refreshes_lifeadmin(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    temp_settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", temp_settings)
    client = TestClient(app_module.app)

    analyzed = client.post(
        "/api/analyze",
        files={"upload": ("scan.txt", b"Zwykly dokument 01.10.2026", "text/plain")},
    )
    assert analyzed.status_code == 200
    doc_id = analyzed.json()["id"]

    corrected = client.patch(
        f"/api/lifepilot/{doc_id}/fields",
        json={
            "document_type": "school",
            "deadline": "2026-10-20",
        },
    )
    assert corrected.status_code == 200
    metadata = corrected.json()["metadata"]
    assert metadata["life_area"] == "children"
    assert metadata["life_event"] == "szkoła"
    assert metadata["reminder_date"] == "2026-10-20"
