import json

from docpilot.config import get_settings
from docpilot.db import (
    add_custom_type,
    add_rule,
    get_setting,
    list_custom_types,
    list_rules,
    set_setting,
)
from docpilot.portable_config import (
    export_portable_config,
    import_portable_config,
    preview_portable_config,
)


def test_export_excludes_credentials_and_machine_specific_paths(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    set_setting(settings, "notification_days", "7")
    set_setting(settings, "background_notifications", "1")
    set_setting(settings, "watch_folder", "C:/Private/Watched")
    set_setting(settings, "google_calendar_client_secret", "C:/Secrets/client_secret.json")
    set_setting(settings, "imap_provider", "gmail")
    set_setting(settings, "imap_email", "user@example.com")
    set_setting(settings, "imap_folder", "Receipts")
    set_setting(settings, "notion_database_id", "notion-db-123")

    add_rule(
        settings,
        {
            "name": "Invoices",
            "condition": {"document_type": "invoice"},
            "target_category": "Finance/Invoices",
            "target_profile": "Company",
            "target_tags": ["finance"],
        },
    )
    add_custom_type(settings, "Warranty", ["warranty", "guarantee"], "Purchases/Warranty")

    payload = export_portable_config(settings)
    serialized = json.dumps(payload)

    assert payload["format"] == "docpilot-portable-config"
    assert payload["format_version"] == 1
    assert payload["preferences"]["notification_days"] == 7
    assert payload["connectors"]["email"]["email"] == "user@example.com"
    assert payload["connectors"]["notion"]["database_id"] == "notion-db-123"
    assert payload["connectors"]["google_calendar"]["configured"] is True
    assert payload["connectors"]["background_notifications"]["enabled"] is True

    assert "C:/Private/Watched" not in serialized
    assert "C:/Secrets/client_secret.json" not in serialized
    assert "notion-token" not in serialized
    assert "app password" not in serialized.lower()
    assert "google-calendar-token.json" in payload["excluded_local_state"]


def test_preview_and_import_are_idempotent_by_name(tmp_path):
    source = get_settings(tmp_path / "Source")
    target = get_settings(tmp_path / "Target")

    set_setting(source, "notification_days", "9")
    set_setting(source, "imap_provider", "outlook")
    set_setting(source, "imap_email", "migrated@example.com")
    set_setting(source, "imap_folder", "Invoices")
    set_setting(source, "notion_database_id", "notion-db-moved")
    set_setting(source, "google_calendar_client_secret", "C:/source/client.json")
    set_setting(source, "background_notifications", "1")

    add_rule(
        source,
        {
            "name": "Invoices",
            "condition": {"document_type": "invoice"},
            "target_category": "Finance/New",
            "target_profile": "Company",
            "target_tags": ["new"],
        },
    )
    disabled_id = add_rule(
        source,
        {
            "name": "Contracts",
            "condition": {"document_type": "contract"},
            "target_category": "Legal/Contracts",
            "target_profile": "Legal Cases",
            "target_tags": [],
        },
    )
    from docpilot.db import update_rule
    update_rule(source, disabled_id, {"enabled": False})
    add_custom_type(source, "Warranty", ["warranty"], "Purchases/Warranty")

    add_rule(
        target,
        {
            "name": "Invoices",
            "condition": {"text_contains": "old"},
            "target_category": "Old",
            "target_profile": "Home",
            "target_tags": ["old"],
        },
    )
    add_custom_type(target, "Warranty", ["old"], "Old/Warranty")
    set_setting(target, "watch_folder", "D:/KeepThis")
    set_setting(target, "google_calendar_client_secret", "D:/keep/client.json")

    payload = export_portable_config(source)
    preview = preview_portable_config(target, payload)

    assert preview["rules"] == {"total": 2, "add": 1, "update": 1}
    assert preview["custom_types"] == {"total": 1, "add": 0, "update": 1}
    assert "Email connector password/app password" in preview["reconnect_required"]
    assert "Notion integration token" in preview["reconnect_required"]
    assert "Google Calendar OAuth client + authorization" in preview["reconnect_required"]
    assert "Background notifications must be re-enabled on this computer" in preview["reconnect_required"]

    result = import_portable_config(target, payload)
    assert result["rules_added"] == 1
    assert result["rules_updated"] == 1
    assert result["custom_types_added"] == 0
    assert result["custom_types_updated"] == 1
    assert result["notification_days"] == 9

    rules = {rule["name"]: rule for rule in list_rules(target)}
    assert set(rules) == {"Invoices", "Contracts"}
    assert rules["Invoices"]["condition"] == {"document_type": "invoice"}
    assert rules["Invoices"]["target_category"] == "Finance/New"
    assert rules["Invoices"]["target_profile"] == "Company"
    assert rules["Invoices"]["target_tags"] == ["new"]
    assert rules["Contracts"]["enabled"] is False

    types = {item["name"]: item for item in list_custom_types(target)}
    assert types["Warranty"]["keywords"] == ["warranty"]
    assert types["Warranty"]["category"] == "Purchases/Warranty"

    assert get_setting(target, "notification_days") == "9"
    assert get_setting(target, "imap_provider") == "outlook"
    assert get_setting(target, "imap_email") == "migrated@example.com"
    assert get_setting(target, "imap_folder") == "Invoices"
    assert get_setting(target, "notion_database_id") == "notion-db-moved"

    # Machine-specific state stays local to the target installation.
    assert get_setting(target, "watch_folder") == "D:/KeepThis"
    assert get_setting(target, "google_calendar_client_secret") == "D:/keep/client.json"
    assert get_setting(target, "background_notifications") is None

    repeated = import_portable_config(target, payload)
    assert repeated["rules_added"] == 0
    assert repeated["rules_updated"] == 2
    assert repeated["custom_types_added"] == 0
    assert repeated["custom_types_updated"] == 1
    assert len(list_rules(target)) == 2
    assert len(list_custom_types(target)) == 1


def test_invalid_portable_config_is_rejected(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")

    try:
        preview_portable_config(settings, {"format": "other", "format_version": 1})
    except ValueError as exc:
        assert "not a DocPilot" in str(exc)
    else:
        raise AssertionError("invalid config format should fail")

    try:
        preview_portable_config(settings, {"format": "docpilot-portable-config", "format_version": 99})
    except ValueError as exc:
        assert "Unsupported configuration format version" in str(exc)
    else:
        raise AssertionError("unsupported version should fail")
