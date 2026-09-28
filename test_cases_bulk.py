import importlib
from datetime import date, timedelta

from fastapi.testclient import TestClient

from docpilot.config import get_settings


def _date_text(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _upload_invoice(client: TestClient, name: str, due: date) -> int:
    document_date = date.today()
    content = (
        f"ACME Sp. z o.o.\nFaktura VAT nr {name}\n"
        f"Data: {_date_text(document_date)}\n"
        f"Termin płatności: {_date_text(due)}\n"
        "Do zapłaty 100,00 PLN\n"
    ).encode("utf-8")
    response = client.post(
        "/api/analyze",
        files={"upload": (f"{name}.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    return int(response.json()["id"])


def test_bulk_metadata_update_and_case_summary(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    today = date.today()
    first_id = _upload_invoice(client, "BULK-1", today + timedelta(days=12))
    second_id = _upload_invoice(client, "BULK-2", today + timedelta(days=5))
    third_id = _upload_invoice(client, "BULK-3", today - timedelta(days=3))

    bulk = client.post(
        "/api/documents/batch-update",
        json={
            "ids": [first_id, second_id],
            "fields": {
                "case_name": "ACME 2026",
                "profile": "Legal Cases",
                "action_required": "to-review",
            },
        },
    )
    assert bulk.status_code == 200
    assert bulk.json()["requested"] == 2
    assert bulk.json()["updated"] == 2

    third = client.patch(
        f"/api/documents/{third_id}",
        json={"case_name": "ACME 2026", "action_required": None},
    )
    assert third.status_code == 200

    documents = client.get("/api/documents?limit=100").json()
    by_id = {int(item["id"]): item for item in documents}
    assert by_id[first_id]["profile"] == "Legal Cases"
    assert by_id[first_id]["case_name"] == "ACME 2026"
    assert by_id[first_id]["action_required"] == "to-review"
    assert by_id[second_id]["profile"] == "Legal Cases"
    assert by_id[third_id]["profile"] == "Home"
    assert by_id[third_id]["action_required"] is None

    cases = client.get("/api/cases")
    assert cases.status_code == 200
    acme = next(item for item in cases.json() if item["name"] == "ACME 2026")
    assert acme["document_count"] == 3
    assert acme["open_actions"] == 2
    assert acme["profiles"] == ["Home", "Legal Cases"]
    assert acme["next_deadline"] == (today + timedelta(days=5)).isoformat()
    assert acme["overdue_deadlines"] == 1
    assert {int(item["id"]) for item in acme["timeline"]} == {first_id, second_id, third_id}
    assert all("path" in item for item in acme["timeline"])
    assert all("document_type" in item for item in acme["timeline"])

    audit = client.get("/api/audit?limit=50")
    assert audit.status_code == 200
    batch_event = next(item for item in audit.json() if item["event"] == "documents-batch-update")
    assert batch_event["payload"]["updated"] == 2
    assert batch_event["payload"]["fields"]["case_name"] == "ACME 2026"


def test_bulk_update_can_clear_case_and_action(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    doc_id = _upload_invoice(client, "CLEAR-1", date.today() + timedelta(days=7))
    assigned = client.post(
        "/api/documents/batch-update",
        json={"ids": [doc_id], "fields": {"case_name": "Temporary", "action_required": "to-pay"}},
    )
    assert assigned.status_code == 200

    cleared = client.post(
        "/api/documents/batch-update",
        json={"ids": [doc_id], "fields": {"case_name": None, "action_required": None}},
    )
    assert cleared.status_code == 200
    document = next(item for item in client.get("/api/documents").json() if int(item["id"]) == doc_id)
    assert document["case_name"] is None
    assert document["action_required"] is None


def test_bulk_update_rejects_empty_or_oversized_requests(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    assert client.post("/api/documents/batch-update", json={"ids": [], "fields": {"profile": "Home"}}).status_code == 400
    assert client.post("/api/documents/batch-update", json={"ids": [1], "fields": {}}).status_code == 400
    assert client.post(
        "/api/documents/batch-update",
        json={"ids": list(range(1, 502)), "fields": {"profile": "Home"}},
    ).status_code == 400
