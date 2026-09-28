import importlib
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot import integration_registry


def _client(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    return app_module, settings, TestClient(app_module.app)


def _upload(client: TestClient, name: str, *, deadline: date | None = None) -> int:
    lines = [
        "ACME Sp. z o.o.",
        f"Faktura VAT nr {name}",
        f"Data: {date.today().strftime('%d.%m.%Y')}",
        "Do zapłaty 100,00 PLN",
    ]
    if deadline:
        lines.append(f"Termin płatności: {deadline.strftime('%d.%m.%Y')}")
    response = client.post(
        "/api/analyze",
        files={"upload": (f"{name}.txt", "\n".join(lines).encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    return int(response.json()["id"])


def test_integration_preview_filters_scope(monkeypatch, tmp_path):
    _app, _settings, client = _client(monkeypatch, tmp_path)

    first = _upload(client, "SYNC-1", deadline=date.today() + timedelta(days=5))
    second = _upload(client, "SYNC-2", deadline=date.today() + timedelta(days=8))
    third = _upload(client, "SYNC-3")

    assert client.patch(
        f"/api/documents/{first}",
        json={"profile": "Company", "case_name": "ACME", "action_required": "to-review", "category": "Finance/Invoices"},
    ).status_code == 200
    assert client.patch(
        f"/api/documents/{second}",
        json={"profile": "Home", "case_name": "ACME", "action_required": "to-review", "category": "Finance/Invoices"},
    ).status_code == 200
    assert client.patch(
        f"/api/documents/{third}",
        json={"profile": "Company", "case_name": "Other", "action_required": "to-review", "category": "Finance/Invoices"},
    ).status_code == 200

    payload = {
        "provider": "notion",
        "scope": {
            "profile": "Company",
            "case_name": "ACME",
            "action_required": "to-review",
            "category": "Finance",
            "limit": 100,
        },
    }
    preview = client.post("/api/integrations/preview", json=payload)
    assert preview.status_code == 200
    data = preview.json()
    assert data["matched_total"] == 1
    assert data["eligible"] == 1
    assert data["sample"][0]["id"] == first

    calendar = client.post("/api/integrations/preview", json={**payload, "provider": "google_calendar"})
    assert calendar.status_code == 200
    assert calendar.json()["eligible"] == 1


def test_notion_sync_records_scope_and_history(monkeypatch, tmp_path):
    app_module, _settings, client = _client(monkeypatch, tmp_path)

    first = _upload(client, "NOTION-1")
    second = _upload(client, "NOTION-2")
    client.patch(f"/api/documents/{first}", json={"profile": "Company", "case_name": "Invoices"})
    client.patch(f"/api/documents/{second}", json={"profile": "Home", "case_name": "Invoices"})

    received = {}

    def fake_sync(_settings, documents, limit=100):
        received["ids"] = [int(item["id"]) for item in documents]
        received["limit"] = limit
        return {"synced": len(documents), "errors": []}

    monkeypatch.setattr(integration_registry, "sync_notion", fake_sync)

    response = client.post(
        "/api/integrations/notion/sync",
        json={"scope": {"profile": "Company", "case_name": "Invoices", "limit": 50}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["attempted"] == 1
    assert data["synced"] == 1
    assert received["ids"] == [first]
    assert received["limit"] == 1

    history = client.get("/api/integrations/history?provider=notion")
    assert history.status_code == 200
    run = history.json()[0]
    assert run["provider"] == "notion"
    assert run["operation"] == "sync"
    assert run["status"] == "success"
    assert run["attempted"] == 1
    assert run["succeeded"] == 1
    assert run["failed"] == 0
    assert run["scope"]["profile"] == "Company"
    assert run["scope"]["case_name"] == "Invoices"


def test_google_sync_records_partial_result(monkeypatch, tmp_path):
    app_module, _settings, client = _client(monkeypatch, tmp_path)

    first = _upload(client, "CAL-1", deadline=date.today() + timedelta(days=3))
    second = _upload(client, "CAL-2", deadline=date.today() + timedelta(days=4))
    client.patch(f"/api/documents/{first}", json={"profile": "Company"})
    client.patch(f"/api/documents/{second}", json={"profile": "Company"})

    def fake_calendar(_settings, documents, calendar_id="primary"):
        assert calendar_id == "team"
        assert {int(item["id"]) for item in documents} == {first, second}
        return {"synced": 1, "errors": ["CAL-2: remote error"]}

    monkeypatch.setattr(integration_registry, "sync_google_calendar", fake_calendar)

    response = client.post(
        "/api/integrations/google-calendar/sync",
        json={"calendar_id": "team", "scope": {"profile": "Company", "limit": 100}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["attempted"] == 2
    assert data["synced"] == 1
    assert len(data["errors"]) == 1

    run = client.get("/api/integrations/history?provider=google_calendar").json()[0]
    assert run["status"] == "partial"
    assert run["attempted"] == 2
    assert run["succeeded"] == 1
    assert run["failed"] == 1
    assert run["scope"]["calendar_id"] == "team"


def test_email_import_records_successful_run(monkeypatch, tmp_path):
    app_module, _settings, client = _client(monkeypatch, tmp_path)
    attachment = tmp_path / "mail-attachment.txt"
    attachment.write_text("Invoice attachment 42 PLN", encoding="utf-8")

    monkeypatch.setattr(
        app_module,
        "import_imap_attachments",
        lambda *_args, **_kwargs: [
            {"path": str(attachment), "name": attachment.name, "subject": "Test", "from": "sender@example.com"}
        ],
    )
    monkeypatch.setattr(
        app_module,
        "_analyze_and_index",
        lambda path: {"id": 77, "source_name": Path(path).name, "source_path": str(path)},
    )

    response = client.post("/api/email/import-imap", json={"unread_only": True, "max_messages": 10})
    assert response.status_code == 200
    assert response.json()["run_id"] > 0
    assert response.json()["errors"] == []

    run = client.get("/api/integrations/history?provider=email").json()[0]
    assert run["status"] == "success"
    assert run["attempted"] == 1
    assert run["succeeded"] == 1
    assert run["scope"]["unread_only"] is True
    assert run["scope"]["max_messages"] == 10


def test_failed_sync_is_retained_in_history(monkeypatch, tmp_path):
    app_module, _settings, client = _client(monkeypatch, tmp_path)
    doc_id = _upload(client, "FAIL-1")
    client.patch(f"/api/documents/{doc_id}", json={"profile": "Company"})

    def fail_sync(*_args, **_kwargs):
        raise RuntimeError("remote service unavailable")

    monkeypatch.setattr(integration_registry, "sync_notion", fail_sync)

    response = client.post(
        "/api/integrations/notion/sync",
        json={"scope": {"profile": "Company", "limit": 20}},
    )
    assert response.status_code == 400

    run = client.get("/api/integrations/history?provider=notion").json()[0]
    assert run["status"] == "failed"
    assert run["attempted"] == 1
    assert run["failed"] == 1
    assert "remote service unavailable" in run["errors"][0]
