from datetime import date

from docpilot.config import get_settings
from docpilot.db import init_db
from docpilot.lifepilot import attention_signature
from docpilot import notifier


def _doc(doc_id: int, *, deadline: str, action: str = "to-pay", confidence: float = 0.95):
    return {
        "id": doc_id,
        "source_name": f"doc-{doc_id}.pdf",
        "path": f"C:/Docs/doc-{doc_id}.pdf",
        "sha256": f"hash-{doc_id}",
        "category": "Finance/Invoices",
        "profile": "Home",
        "case_name": None,
        "action_required": action,
        "metadata": {
            "document_type": "invoice",
            "issuer": "ACME",
            "deadline": deadline,
            "confidence": confidence,
            "amount": 100.0,
            "currency": "PLN",
        },
    }


def test_collect_notification_items_uses_lifepilot_horizon_and_handled_state():
    today = date(2026, 10, 4)
    due_today = _doc(1, deadline="2026-10-04")
    due_soon = _doc(2, deadline="2026-10-06")
    too_far = _doc(3, deadline="2026-10-10")
    too_old = _doc(4, deadline="2026-09-20")
    handled = _doc(5, deadline="2026-10-05")
    low_confidence = _doc(6, deadline="2026-10-05", action="to-review", confidence=0.4)

    handled_map = {
        "5": {
            "version": 2,
            "signature": attention_signature(handled),
            "done_at": "2026-10-04T09:00:00+00:00",
        }
    }

    items = notifier.collect_notification_items(
        [due_today, due_soon, too_far, too_old, handled, low_confidence],
        handled_map,
        days_ahead=3,
        today=today,
    )

    assert [item["id"] for item in items] == [1, 2, 6]
    assert all(item["id"] != 5 for item in items)
    assert all(item["id"] != 3 for item in items)
    assert all(item["id"] != 4 for item in items)
    review = next(item for item in items if item["id"] == 6)
    assert review["priority"] == "urgent"
    assert "sprawdź" in review["title"].lower()
    assert review["verification"]["source"] == "automatic"


def test_notify_once_deduplicates_same_state_but_allows_meaningful_change(monkeypatch, tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    init_db(settings)
    today = date(2026, 10, 4)
    shown = []

    item = {
        "id": 7,
        "name": "invoice.pdf",
        "date": "2026-10-06",
        "days": 2,
        "action": "to-pay",
        "title": "Zweryfikuj i opłać dokument",
        "priority": "urgent",
        "verification": {"source": "automatic", "confidence": 0.95},
        "signature": "state-a",
    }

    current = [item]
    monkeypatch.setattr(notifier, "collect_due", lambda *args, **kwargs: list(current))
    monkeypatch.setattr(notifier, "_toast", lambda title, message: shown.append((title, message)))

    assert notifier.notify_once(3, settings=settings, today=today) == 1
    assert notifier.notify_once(3, settings=settings, today=today) == 0
    assert len(shown) == 1
    assert shown[0][0] == "LifePilot · Co teraz?"
    assert "Zweryfikuj i opłać dokument" in shown[0][1]

    current[0] = {**item, "date": "2026-10-05", "days": 1, "signature": "state-b"}
    assert notifier.notify_once(3, settings=settings, today=today) == 1
    assert len(shown) == 2
