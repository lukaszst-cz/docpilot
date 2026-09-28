from __future__ import annotations

import email
import hashlib
import imaplib
import json
from datetime import date
from email import policy
from pathlib import Path
from typing import Any, Callable

from .db import get_integration_link, get_setting, set_setting, upsert_integration_link

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


def _fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _notion_sync_payload(document: dict[str, Any], database_id: str, title_prop: str) -> tuple[dict[str, Any], str]:
    md = document.get("metadata") or {}
    children = [{
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{
                "type": "text",
                "text": {"content": f"Local source: {document.get('path')}"},
            }]
        },
    }]
    if md.get("deadline"):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"Deadline: {md.get('deadline')}"},
                }]
            },
        })
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            title_prop: {
                "title": [{
                    "type": "text",
                    "text": {"content": str(document.get("source_name") or "Document")[:1800]},
                }]
            }
        },
        "children": children,
    }
    fingerprint = _fingerprint({
        "source_name": document.get("source_name"),
        "path": document.get("path"),
        "deadline": md.get("deadline"),
    })
    return payload, fingerprint


def _calendar_event(document: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    md = document.get("metadata") or {}
    raw = md.get("deadline") or md.get("warranty_until")
    if not raw:
        return None, None
    event = {
        "summary": f"DocPilot: {document.get('action_required') or 'deadline'} — {document.get('source_name')}",
        "description": f"Local document: {document.get('path')}",
        "start": {"date": str(raw)},
        "end": {"date": str(raw)},
        "extendedProperties": {"private": {"docpilotId": str(document.get("id"))}},
    }
    return event, _fingerprint(event)


def configure_notion(settings, token: str, database_id: str) -> dict[str, Any]:
    save_secret("notion-token", token)
    set_setting(settings, "notion_database_id", database_id.strip())
    return notion_status(settings)


def notion_status(settings) -> dict[str, Any]:
    db = get_setting(settings, "notion_database_id")
    return {"configured": bool(db and get_secret("notion-token")), "database_id": db}


def _notion_requests():
    try:
        import requests
        return requests
    except ImportError as exc:
        raise RuntimeError("Notion sync requires the integrations dependency (requests).") from exc


def sync_notion(settings, documents: list[dict[str, Any]], limit: int = 100) -> dict[str, Any]:
    requests = _notion_requests()

    token = get_secret("notion-token")
    database_id = get_setting(settings, "notion_database_id")
    if not token or not database_id:
        raise RuntimeError("Notion is not configured.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    meta = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=20)
    meta.raise_for_status()
    properties = meta.json().get("properties") or {}
    title_prop = next((name for name, p in properties.items() if p.get("type") == "title"), None)
    if not title_prop:
        raise RuntimeError("The selected Notion database has no title property.")

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for document in documents[:max(1, min(limit, 500))]:
        payload, fingerprint = _notion_sync_payload(document, database_id, title_prop)
        document_id = int(document["id"])
        link = get_integration_link(settings, "notion", document_id)

        if link and link.get("fingerprint") == fingerprint:
            skipped += 1
            continue

        try:
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            page = response.json()
            new_page_id = str(page.get("id") or "")
            if not new_page_id:
                raise RuntimeError("Notion did not return a page ID.")

            if link:
                try:
                    archive = requests.patch(
                        f"https://api.notion.com/v1/pages/{link['external_id']}",
                        headers=headers,
                        json={"archived": True},
                        timeout=20,
                    )
                    archive.raise_for_status()
                except Exception:
                    try:
                        rollback = requests.patch(
                            f"https://api.notion.com/v1/pages/{new_page_id}",
                            headers=headers,
                            json={"archived": True},
                            timeout=20,
                        )
                        rollback.raise_for_status()
                    except Exception:
                        pass
                    raise

            upsert_integration_link(
                settings,
                provider="notion",
                document_id=document_id,
                external_id=new_page_id,
                fingerprint=fingerprint,
                external_url=page.get("url"),
            )
            if link:
                updated += 1
            else:
                created += 1
        except Exception as exc:
            errors.append(f"{document.get('source_name')}: {exc}")

    return {
        "synced": created + updated,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
    }

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


def _google_calendar_service(settings):
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
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def sync_google_calendar(settings, documents: list[dict[str, Any]], calendar_id: str = "primary") -> dict[str, Any]:
    service = _google_calendar_service(settings)
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for document in documents:
        event, fingerprint = _calendar_event(document)
        if not event or not fingerprint:
            continue

        document_id = int(document["id"])
        link = get_integration_link(settings, "google_calendar", document_id)

        if link and link.get("fingerprint") == fingerprint:
            skipped += 1
            continue

        try:
            if link:
                response = service.events().update(
                    calendarId=calendar_id,
                    eventId=link["external_id"],
                    body=event,
                ).execute()
                updated += 1
            else:
                response = service.events().insert(
                    calendarId=calendar_id,
                    body=event,
                ).execute()
                created += 1

            external_id = str(response.get("id") or (link or {}).get("external_id") or "")
            if not external_id:
                raise RuntimeError("Google Calendar did not return an event ID.")

            upsert_integration_link(
                settings,
                provider="google_calendar",
                document_id=document_id,
                external_id=external_id,
                fingerprint=fingerprint,
                external_url=response.get("htmlLink"),
            )
        except Exception as exc:
            errors.append(f"{document.get('source_name')}: {exc}")

    return {
        "synced": created + updated,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
    }
