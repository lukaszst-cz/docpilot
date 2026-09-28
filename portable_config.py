from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import __version__
from .db import (
    add_custom_type,
    add_rule,
    get_setting,
    list_custom_types,
    list_rules,
    set_setting,
    update_rule,
)


FORMAT_NAME = "docpilot-portable-config"
FORMAT_VERSION = 1


def export_portable_config(settings) -> dict[str, Any]:
    email_address = get_setting(settings, "imap_email")
    notion_database_id = get_setting(settings, "notion_database_id")
    google_client = get_setting(settings, "google_calendar_client_secret")
    background_notifications = get_setting(settings, "background_notifications", "0") == "1"

    return {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "docpilot_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "preferences": {
            "notification_days": int(get_setting(settings, "notification_days", "3") or 3),
        },
        "rules": [
            {
                "name": rule["name"],
                "condition": rule.get("condition") or {},
                "target_category": rule.get("target_category"),
                "target_profile": rule.get("target_profile"),
                "target_tags": rule.get("target_tags") or [],
                "enabled": bool(rule.get("enabled", True)),
            }
            for rule in list_rules(settings)
        ],
        "custom_types": [
            {
                "name": item["name"],
                "keywords": item.get("keywords") or [],
                "category": item.get("category") or "Documents",
            }
            for item in list_custom_types(settings)
        ],
        "connectors": {
            "email": {
                "configured": bool(email_address),
                "provider": get_setting(settings, "imap_provider"),
                "email": email_address,
                "folder": get_setting(settings, "imap_folder", "INBOX"),
                "credential_included": False,
            },
            "notion": {
                "configured": bool(notion_database_id),
                "database_id": notion_database_id,
                "token_included": False,
            },
            "google_calendar": {
                "configured": bool(google_client),
                "oauth_files_included": False,
            },
            "background_notifications": {
                "enabled": background_notifications,
                "startup_registration_included": False,
            },
        },
        "excluded_local_state": [
            "watch_folder",
            "google_calendar_client_secret",
            "google-calendar-token.json",
            "integration credentials",
            "notification startup registration",
            "integration links and run history",
        ],
    }


def _validate(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Configuration must be a JSON object.")
    if payload.get("format") != FORMAT_NAME:
        raise ValueError("This is not a DocPilot portable configuration file.")
    if int(payload.get("format_version") or 0) != FORMAT_VERSION:
        raise ValueError(f"Unsupported configuration format version: {payload.get('format_version')}")


def _reconnect_requirements(payload: dict[str, Any]) -> list[str]:
    connectors = payload.get("connectors") or {}
    required: list[str] = []
    if (connectors.get("email") or {}).get("configured"):
        required.append("Email connector password/app password")
    if (connectors.get("notion") or {}).get("configured"):
        required.append("Notion integration token")
    if (connectors.get("google_calendar") or {}).get("configured"):
        required.append("Google Calendar OAuth client + authorization")
    if (connectors.get("background_notifications") or {}).get("enabled"):
        required.append("Background notifications must be re-enabled on this computer")
    return required


def preview_portable_config(settings, payload: dict[str, Any]) -> dict[str, Any]:
    _validate(payload)

    existing_rules = {rule["name"]: rule for rule in list_rules(settings)}
    existing_types = {item["name"]: item for item in list_custom_types(settings)}
    incoming_rules = [item for item in (payload.get("rules") or []) if isinstance(item, dict) and str(item.get("name") or "").strip()]
    incoming_types = [item for item in (payload.get("custom_types") or []) if isinstance(item, dict) and str(item.get("name") or "").strip()]

    return {
        "format_version": FORMAT_VERSION,
        "source_docpilot_version": payload.get("docpilot_version"),
        "rules": {
            "total": len(incoming_rules),
            "add": sum(1 for item in incoming_rules if str(item.get("name")) not in existing_rules),
            "update": sum(1 for item in incoming_rules if str(item.get("name")) in existing_rules),
        },
        "custom_types": {
            "total": len(incoming_types),
            "add": sum(1 for item in incoming_types if str(item.get("name")) not in existing_types),
            "update": sum(1 for item in incoming_types if str(item.get("name")) in existing_types),
        },
        "reconnect_required": _reconnect_requirements(payload),
        "excluded_local_state": list(payload.get("excluded_local_state") or []),
    }


def import_portable_config(settings, payload: dict[str, Any]) -> dict[str, Any]:
    preview = preview_portable_config(settings, payload)

    rules_by_name = {rule["name"]: rule for rule in list_rules(settings)}
    added_rules = 0
    updated_rules = 0
    for incoming in payload.get("rules") or []:
        if not isinstance(incoming, dict):
            continue
        name = str(incoming.get("name") or "").strip()
        if not name:
            continue
        rule_payload = {
            "name": name,
            "condition": incoming.get("condition") if isinstance(incoming.get("condition"), dict) else {},
            "target_category": incoming.get("target_category"),
            "target_profile": incoming.get("target_profile"),
            "target_tags": [str(tag) for tag in (incoming.get("target_tags") or [])],
            "enabled": bool(incoming.get("enabled", True)),
        }
        existing = rules_by_name.get(name)
        if existing:
            update_rule(settings, int(existing["id"]), rule_payload)
            updated_rules += 1
        else:
            rule_id = add_rule(settings, rule_payload)
            if not rule_payload["enabled"]:
                update_rule(settings, rule_id, {"enabled": False})
            rules_by_name[name] = {"id": rule_id, **rule_payload}
            added_rules += 1

    existing_types = {item["name"]: item for item in list_custom_types(settings)}
    added_types = 0
    updated_types = 0
    for incoming in payload.get("custom_types") or []:
        if not isinstance(incoming, dict):
            continue
        name = str(incoming.get("name") or "").strip()
        if not name:
            continue
        keywords = [str(keyword) for keyword in (incoming.get("keywords") or [])]
        category = str(incoming.get("category") or "Documents")
        if name in existing_types:
            updated_types += 1
        else:
            added_types += 1
        add_custom_type(settings, name, keywords, category)

    preferences = payload.get("preferences") or {}
    try:
        notification_days = max(0, min(int(preferences.get("notification_days") or 3), 30))
    except (TypeError, ValueError):
        notification_days = 3
    set_setting(settings, "notification_days", str(notification_days))

    connectors = payload.get("connectors") or {}
    email_config = connectors.get("email") or {}
    if email_config.get("configured"):
        provider = str(email_config.get("provider") or "").lower()
        if provider in {"gmail", "outlook"}:
            set_setting(settings, "imap_provider", provider)
        email_address = str(email_config.get("email") or "").strip()
        if email_address:
            set_setting(settings, "imap_email", email_address)
        set_setting(settings, "imap_folder", str(email_config.get("folder") or "INBOX"))

    notion_config = connectors.get("notion") or {}
    if notion_config.get("configured"):
        database_id = str(notion_config.get("database_id") or "").strip()
        if database_id:
            set_setting(settings, "notion_database_id", database_id)

    return {
        "rules_added": added_rules,
        "rules_updated": updated_rules,
        "custom_types_added": added_types,
        "custom_types_updated": updated_types,
        "notification_days": notification_days,
        "reconnect_required": preview["reconnect_required"],
    }
