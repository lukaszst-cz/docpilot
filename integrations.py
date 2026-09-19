from __future__ import annotations

import email
import imaplib
import json
from datetime import date
from email import policy
from pathlib import Path
from typing import Any, Callable

from .db import get_setting, set_setting

_SERVICE = "DocPilot"


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError as exc:
        raise RuntimeError("Secure credential storage requires the integrations dependency (keyring).") from exc


def save_secret(name: str, value: str) -> None:
    _keyring().set_password(_SERVICE, name, value)


def get_secret(name: str) -> str | None:
    return _keyring().get_password(_SERVICE, name)


def delete_secret(name: str) -> None:
    try:
        _keyring().delete_password(_SERVICE, name)
    except Exception:
        pass


def configure_imap(settings, *, provider: str, email_address: str, password: str, folder: str = "INBOX") -> dict[str, Any]:
    provider = provider.lower()
    host = {"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}.get(provider)
    if not host:
        raise ValueError("provider must be gmail or outlook")
    save_secret(f"imap:{email_address}", password)
    set_setting(settings, "imap_provider", provider)
    set_setting(settings, "imap_email", email_address)
    set_setting(settings, "imap_folder", folder or "INBOX")
    return {"provider": provider, "email": email_address, "folder": folder or "INBOX"}


def imap_status(settings) -> dict[str, Any]:
    email_address = get_setting(settings, "imap_email")
    return {
        "configured": bool(email_address),
        "provider": get_setting(settings, "imap_provider"),
        "email": email_address,
        "folder": get_setting(settings, "imap_folder", "INBOX"),
        "secret_available": bool(get_secret(f"imap:{email_address}")) if email_address else False,
    }


def import_imap_attachments(settings, destination_factory: Callable[[str], Path], *, unread_only: bool = True, max_messages: int = 20) -> list[dict[str, Any]]:
    status = imap_status(settings)
    if not status["configured"] or not status["secret_available"]:
        raise RuntimeError("Email connector is not configured.")
    provider = status["provider"]
    host = {"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}[provider]
    user = status["email"]
    password = get_secret(f"imap:{user}")
    imported: list[dict[str, Any]] = []
    with imaplib.IMAP4_SSL(host) as client:
        client.login(user, password)
        client.select(status["folder"] or "INBOX")
        criterion = "UNSEEN" if unread_only else "ALL"
        typ, data = client.search(None, criterion)
        if typ != "OK":
            return []
        ids = data[0].split()[-max(1, min(max_messages, 100)):]
        for msg_id in reversed(ids):
            typ, msg_data = client.fetch(msg_id, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            raw = next((part[1] for part in msg_data if isinstance(part, tuple)), None)
            if not raw:
                continue
            msg = email.message_from_bytes(raw, policy=policy.default)
            for part in msg.iter_attachments():
                filename = part.get_filename() or "attachment"
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                path = destination_factory(filename)
                path.write_bytes(payload)
                imported.append({"path": str(path), "name": filename, "subject": msg.get("subject"), "from": msg.get("from")})
    return imported


def configure_notion(settings, token: str, database_id: str) -> dict[str, Any]:
    save_secret("notion-token", token)
    set_setting(settings, "notion_database_id", database_id.strip())
    return notion_status(settings)


def notion_status(settings) -> dict[str, Any]:
    db = get_setting(settings, "notion_database_id")
    return {"configured": bool(db and get_secret("notion-token")), "database_id": db}


def sync_notion(settings, documents: list[dict[str, Any]], limit: int = 100) -> dict[str, Any]:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Notion sync requires the integrations dependency (requests).") from exc
    token = get_secret("notion-token")
    database_id = get_setting(settings, "notion_database_id")
    if not token or not database_id:
        raise RuntimeError("Notion is not configured.")
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    meta = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=20)
    meta.raise_for_status()
    properties = meta.json().get("properties") or {}
    title_prop = next((name for name, p in properties.items() if p.get("type") == "title"), None)
    if not title_prop:
        raise RuntimeError("The selected Notion database has no title property.")
    synced = 0
    errors: list[str] = []
    for d in documents[:max(1, min(limit, 500))]:
        md = d.get("metadata") or {}
        children = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Local source: {d.get('path')}"}}]}}]
        if md.get("deadline"):
            children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Deadline: {md.get('deadline')}"}}]}})
        payload = {"parent": {"database_id": database_id}, "properties": {title_prop: {"title": [{"type": "text", "text": {"content": str(d.get('source_name') or 'Document')[:1800]}}]}}, "children": children}
        try:
            r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=20)
            r.raise_for_status()
            synced += 1
        except Exception as exc:
            errors.append(f"{d.get('source_name')}: {exc}")
    return {"synced": synced, "errors": errors[:20]}


def google_calendar_status(settings) -> dict[str, Any]:
    client_path = get_setting(settings, "google_calendar_client_secret")
    token_path = settings.state / "google-calendar-token.json"
    return {"configured": bool(client_path and Path(client_path).exists()), "authorized": token_path.exists(), "client_secret": client_path}


def configure_google_calendar(settings, client_secret_path: str) -> dict[str, Any]:
    path = Path(client_secret_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    set_setting(settings, "google_calendar_client_secret", str(path))
    return google_calendar_status(settings)


def sync_google_calendar(settings, documents: list[dict[str, Any]], calendar_id: str = "primary") -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google Calendar sync requires the calendar optional dependency.") from exc

    scopes = ["https://www.googleapis.com/auth/calendar.events"]
    status = google_calendar_status(settings)
    client_path = status.get("client_secret")
    if not client_path:
        raise RuntimeError("Google Calendar OAuth client file is not configured.")
    token_path = settings.state / "google-calendar-token.json"
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes)
            creds = flow.run_local_server(port=0, open_browser=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    synced = 0
    errors: list[str] = []
    for d in documents:
        md = d.get("metadata") or {}
        raw = md.get("deadline") or md.get("warranty_until")
        if not raw:
            continue
        event = {
            "summary": f"DocPilot: {d.get('action_required') or 'deadline'} — {d.get('source_name')}",
            "description": f"Local document: {d.get('path')}",
            "start": {"date": str(raw)},
            "end": {"date": str(raw)},
            "extendedProperties": {"private": {"docpilotId": str(d.get("id"))}},
        }
        try:
            service.events().insert(calendarId=calendar_id, body=event).execute()
            synced += 1
        except Exception as exc:
            errors.append(f"{d.get('source_name')}: {exc}")
    return {"synced": synced, "errors": errors[:20]}
