from datetime import date, timedelta

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.integration_registry import (
    IntegrationAdapter,
    get_integration_adapter,
    integration_catalog,
    register_integration_adapter,
    unregister_integration_adapter,
)


def test_builtin_integration_catalog_describes_capabilities(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    catalog = {item["key"]: item for item in integration_catalog(settings)}

    assert set(catalog) >= {"email", "notion", "google_calendar"}
    assert catalog["email"]["direction"] == "import"
    assert catalog["email"]["supports_document_sync"] is False
    assert catalog["notion"]["supports_scope"] is True
    assert catalog["notion"]["idempotent"] is True
    assert catalog["google_calendar"]["supports_document_sync"] is True
    assert catalog["google_calendar"]["idempotent"] is True


def test_new_document_sync_adapter_is_available_to_app_without_app_changes(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    monkeypatch.setattr(app_module, "settings", settings)

    calls = {}

    def status(_settings):
        return {"configured": True}

    def sync(_settings, documents, options):
        calls["ids"] = [int(document["id"]) for document in documents]
        calls["options"] = options
        return {"synced": len(documents), "created": len(documents), "updated": 0, "skipped": 0, "errors": []}

    adapter = IntegrationAdapter(
        key="demo_export",
        label="Demo Export",
        direction="export",
        status_fn=status,
        document_sync_fn=sync,
        eligibility_fn=lambda document: (document.get("metadata") or {}).get("document_type") == "invoice",
        supports_scope=True,
        idempotent=True,
    )
    register_integration_adapter(adapter)

    try:
        assert get_integration_adapter("demo_export") is adapter
        client = TestClient(app_module.app)

        content = (
            "ACME Sp. z o.o.\n"
            "Faktura VAT nr DEMO/1\n"
            f"Data: {date.today().strftime('%d.%m.%Y')}\n"
            f"Termin płatności: {(date.today()+timedelta(days=5)).strftime('%d.%m.%Y')}\n"
            "Do zapłaty 100,00 PLN\n"
        ).encode("utf-8")
        uploaded = client.post(
            "/api/analyze",
            files={"upload": ("demo-invoice.txt", content, "text/plain")},
        )
        assert uploaded.status_code == 200
        doc_id = int(uploaded.json()["id"])

        catalog = client.get("/api/integrations/catalog")
        assert catalog.status_code == 200
        demo = next(item for item in catalog.json() if item["key"] == "demo_export")
        assert demo["label"] == "Demo Export"
        assert demo["supports_document_sync"] is True

        preview = client.post(
            "/api/integrations/preview",
            json={"provider": "demo_export", "scope": {"limit": 20}},
        )
        assert preview.status_code == 200
        assert preview.json()["eligible"] == 1
        assert preview.json()["sample"][0]["id"] == doc_id

        # The generic adapter contract can execute the provider without adding
        # provider-specific logic to app.py.
        result = adapter.sync_documents(settings, [uploaded.json()], {"mode": "test"})
        assert result["synced"] == 1
        assert calls["ids"] == [doc_id]
        assert calls["options"] == {"mode": "test"}
    finally:
        unregister_integration_adapter("demo_export")
