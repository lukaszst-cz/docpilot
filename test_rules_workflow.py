import importlib

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.rules import apply_rules, rule_matches


def test_newer_matching_rule_overrides_older_rule_and_keeps_trace():
    document = {
        "category": "Documents",
        "profile": "Home",
        "tags": ["base"],
        "extracted_text": "ACME monthly invoice",
        "metadata": {"issuer": "ACME", "document_type": "invoice"},
    }
    rules = [
        {
            "id": 1,
            "name": "Older",
            "enabled": True,
            "condition": {"document_type": "invoice"},
            "target_category": "Finance/Invoices",
            "target_profile": "Home",
            "target_tags": ["invoice"],
        },
        {
            "id": 2,
            "name": "Newer",
            "enabled": True,
            "condition": {"issuer_contains": "ACME"},
            "target_category": "Finance/ACME",
            "target_profile": "Company",
            "target_tags": ["acme"],
        },
    ]

    result = apply_rules(document, rules)

    assert result["category"] == "Finance/ACME"
    assert result["profile"] == "Company"
    assert result["tags"] == ["acme", "base", "invoice"]
    assert result["matched_rules"] == [
        {"id": 1, "name": "Older"},
        {"id": 2, "name": "Newer"},
    ]


def test_disabled_rule_and_document_type_condition():
    document = {
        "extracted_text": "quarterly invoice",
        "metadata": {"issuer": "ACME", "document_type": "invoice"},
    }
    disabled = {
        "enabled": False,
        "condition": {"document_type": "invoice"},
    }
    contract_only = {
        "enabled": True,
        "condition": {"document_type": "contract"},
    }
    invoice = {
        "enabled": True,
        "condition": {"document_type": "invoice"},
    }

    assert rule_matches(document, disabled) is False
    assert rule_matches(document, contract_only) is False
    assert rule_matches(document, invoice) is True


def test_rule_crud_and_analysis_trace_through_api(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    older = client.post(
        "/api/rules",
        json={
            "name": "Serial documents",
            "condition": {"text_contains": "serial-marker"},
            "target_category": "Documents/Serial",
            "target_profile": "Home",
            "target_tags": ["serial"],
        },
    )
    newer = client.post(
        "/api/rules",
        json={
            "name": "ACME serial",
            "condition": {"text_contains": "serial-marker"},
            "target_category": "Finance/ACME",
            "target_profile": "Company",
            "target_tags": ["acme"],
        },
    )
    assert older.status_code == 200
    assert newer.status_code == 200

    older_id = older.json()["id"]
    newer_id = newer.json()["id"]

    listed = client.get("/api/rules")
    assert listed.status_code == 200
    assert [rule["id"] for rule in listed.json()] == [older_id, newer_id]

    analyzed = client.post(
        "/api/analyze",
        files={
            "upload": (
                "serial.txt",
                b"serial-marker ACME invoice total 100 PLN",
                "text/plain",
            )
        },
    )
    assert analyzed.status_code == 200
    payload = analyzed.json()
    assert payload["suggested_category"] == "Finance/ACME"
    assert payload["profile"] == "Company"
    assert payload["matched_rules"] == [
        {"id": older_id, "name": "Serial documents"},
        {"id": newer_id, "name": "ACME serial"},
    ]

    edited = client.patch(
        f"/api/rules/{newer_id}",
        json={
            "name": "ACME contracts",
            "condition": {"document_type": "contract"},
            "target_category": "Contracts/ACME",
            "target_profile": "Legal Cases",
            "target_tags": ["contract", "acme"],
        },
    )
    assert edited.status_code == 200
    edited_rule = edited.json()
    assert edited_rule["name"] == "ACME contracts"
    assert edited_rule["condition"] == {"document_type": "contract"}
    assert edited_rule["target_category"] == "Contracts/ACME"
    assert edited_rule["target_profile"] == "Legal Cases"
    assert edited_rule["target_tags"] == ["contract", "acme"]

    paused = client.patch(f"/api/rules/{newer_id}", json={"enabled": False})
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False

    analyzed_again = client.post(
        "/api/analyze",
        files={
            "upload": (
                "serial-2.txt",
                b"serial-marker second document",
                "text/plain",
            )
        },
    )
    assert analyzed_again.status_code == 200
    second = analyzed_again.json()
    assert second["suggested_category"] == "Documents/Serial"
    assert second["profile"] == "Home"
    assert second["matched_rules"] == [{"id": older_id, "name": "Serial documents"}]

    deleted = client.delete(f"/api/rules/{older_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": older_id}

    remaining = client.get("/api/rules")
    assert remaining.status_code == 200
    assert [rule["id"] for rule in remaining.json()] == [newer_id]
