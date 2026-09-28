from copy import deepcopy

from docpilot.config import get_settings
from docpilot.db import get_integration_link
from docpilot import integrations


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self._payload = payload or {}
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._payload


class FakeNotionRequests:
    def __init__(self):
        self.posts = []
        self.patches = []
        self.next_page = 1

    def get(self, url, **_kwargs):
        return FakeResponse({"properties": {"Name": {"type": "title"}}})

    def post(self, url, **kwargs):
        page_id = f"page-{self.next_page}"
        self.next_page += 1
        self.posts.append({"url": url, "json": kwargs.get("json"), "page_id": page_id})
        return FakeResponse({"id": page_id, "url": f"https://notion.example/{page_id}"})

    def patch(self, url, **kwargs):
        self.patches.append({"url": url, "json": kwargs.get("json")})
        return FakeResponse({"ok": True})


class FakeCalendarRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeCalendarEvents:
    def __init__(self):
        self.inserts = []
        self.updates = []

    def insert(self, *, calendarId, body):
        event_id = f"event-{len(self.inserts)+1}"
        self.inserts.append({"calendar_id": calendarId, "body": body, "id": event_id})
        return FakeCalendarRequest({"id": event_id, "htmlLink": f"https://calendar.example/{event_id}"})

    def update(self, *, calendarId, eventId, body):
        self.updates.append({"calendar_id": calendarId, "event_id": eventId, "body": body})
        return FakeCalendarRequest({"id": eventId, "htmlLink": f"https://calendar.example/{eventId}"})


class FakeCalendarService:
    def __init__(self):
        self.events_api = FakeCalendarEvents()

    def events(self):
        return self.events_api


def _document(doc_id=1):
    return {
        "id": doc_id,
        "source_name": "invoice.txt",
        "path": "/archive/invoice.txt",
        "action_required": "to-pay",
        "metadata": {"deadline": "2026-10-05"},
    }


def test_notion_sync_create_skip_and_replace(monkeypatch, tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    fake = FakeNotionRequests()

    monkeypatch.setattr(integrations, "_notion_requests", lambda: fake)
    monkeypatch.setattr(integrations, "get_secret", lambda name: "token" if name == "notion-token" else None)
    monkeypatch.setattr(
        integrations,
        "get_setting",
        lambda _settings, key, default=None: "db-1" if key == "notion_database_id" else default,
    )

    doc = _document()

    first = integrations.sync_notion(settings, [doc])
    assert first == {"synced": 1, "created": 1, "updated": 0, "skipped": 0, "errors": []}
    assert len(fake.posts) == 1
    assert fake.patches == []
    link = get_integration_link(settings, "notion", 1)
    assert link["external_id"] == "page-1"

    second = integrations.sync_notion(settings, [doc])
    assert second == {"synced": 0, "created": 0, "updated": 0, "skipped": 1, "errors": []}
    assert len(fake.posts) == 1
    assert fake.patches == []

    changed = deepcopy(doc)
    changed["source_name"] = "invoice-updated.txt"
    third = integrations.sync_notion(settings, [changed])
    assert third == {"synced": 1, "created": 0, "updated": 1, "skipped": 0, "errors": []}
    assert len(fake.posts) == 2
    assert fake.patches == [{
        "url": "https://api.notion.com/v1/pages/page-1",
        "json": {"archived": True},
    }]
    link = get_integration_link(settings, "notion", 1)
    assert link["external_id"] == "page-2"


def test_google_calendar_sync_create_skip_and_update(monkeypatch, tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    service = FakeCalendarService()
    monkeypatch.setattr(integrations, "_google_calendar_service", lambda _settings: service)

    doc = _document()

    first = integrations.sync_google_calendar(settings, [doc], calendar_id="primary")
    assert first == {"synced": 1, "created": 1, "updated": 0, "skipped": 0, "errors": []}
    assert len(service.events_api.inserts) == 1
    assert service.events_api.updates == []
    link = get_integration_link(settings, "google_calendar", 1)
    assert link["external_id"] == "event-1"

    second = integrations.sync_google_calendar(settings, [doc], calendar_id="primary")
    assert second == {"synced": 0, "created": 0, "updated": 0, "skipped": 1, "errors": []}
    assert len(service.events_api.inserts) == 1
    assert service.events_api.updates == []

    changed = deepcopy(doc)
    changed["action_required"] = "to-review"
    third = integrations.sync_google_calendar(settings, [changed], calendar_id="primary")
    assert third == {"synced": 1, "created": 0, "updated": 1, "skipped": 0, "errors": []}
    assert len(service.events_api.inserts) == 1
    assert len(service.events_api.updates) == 1
    assert service.events_api.updates[0]["event_id"] == "event-1"
    assert "to-review" in service.events_api.updates[0]["body"]["summary"]
    link = get_integration_link(settings, "google_calendar", 1)
    assert link["external_id"] == "event-1"


def test_provider_fingerprints_ignore_unrelated_local_metadata():
    doc = _document()
    notion_payload, notion_before = integrations._notion_sync_payload(doc, "db", "Name")
    calendar_event, calendar_before = integrations._calendar_event(doc)
    assert notion_payload
    assert calendar_event

    changed = deepcopy(doc)
    changed["profile"] = "Company"
    changed["case_name"] = "Case A"
    changed["category"] = "Finance/Invoices"
    changed["tags"] = ["reviewed"]

    _, notion_after = integrations._notion_sync_payload(changed, "db", "Name")
    _, calendar_after = integrations._calendar_event(changed)

    assert notion_before == notion_after
    assert calendar_before == calendar_after
