import json

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import add_rule, list_rules


def test_portable_config_api_round_trip(monkeypatch, tmp_path):
    import docpilot.app as app_module

    source_settings = get_settings(tmp_path / "Source")
    monkeypatch.setattr(app_module, "settings", source_settings)
    add_rule(source_settings, {"name": "Portable", "condition": {"text_contains": "portable"}})

    client = TestClient(app_module.app)
    exported = client.get("/api/export/config")
    assert exported.status_code == 200
    payload = json.loads(exported.content.decode("utf-8"))
    assert payload["format"] == "docpilot-portable-config"
    assert payload["rules"][0]["name"] == "Portable"

    target_settings = get_settings(tmp_path / "Target")
    monkeypatch.setattr(app_module, "settings", target_settings)

    preview = client.post("/api/config/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json()["rules"]["add"] == 1

    imported = client.post("/api/config/import", json=payload)
    assert imported.status_code == 200
    assert imported.json()["rules_added"] == 1
    assert [rule["name"] for rule in list_rules(target_settings)] == ["Portable"]

    bad = client.post("/api/config/preview", json={"format": "wrong", "format_version": 1})
    assert bad.status_code == 400
