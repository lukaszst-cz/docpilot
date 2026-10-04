from __future__ import annotations

from datetime import date, datetime
from typing import Any


_ACTION_LABELS = {
    "to-pay": "Zweryfikuj i opłać dokument",
    "to-reply": "Przygotuj odpowiedź",
    "to-sign": "Sprawdź i podpisz dokument",
    "to-review": "Sprawdź dokument ręcznie",
    "to-renew": "Sprawdź odnowienie lub przedłużenie",
}


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _priority_for(due: date | None, today: date) -> tuple[str, int | None]:
    if due is None:
        return "normal", None
    days = (due - today).days
    if days < 0:
        return "overdue", days
    if days == 0:
        return "today", days
    if days <= 3:
        return "urgent", days
    if days <= 14:
        return "soon", days
    return "normal", days


def next_action_for_document(document: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    metadata = document.get("metadata") or {}
    deadline = _as_date(metadata.get("deadline") or metadata.get("warranty_until"))
    priority, days_remaining = _priority_for(deadline, today)
    action = str(document.get("action_required") or "").strip()
    confidence = float(metadata.get("confidence") or 0)

    if confidence < 0.65:
        title = "Najpierw sprawdź dane odczytane z dokumentu"
        reason = "Pewność automatycznego rozpoznania jest niska."
        steps = [
            "Porównaj kluczowe dane z oryginałem.",
            "Popraw termin, kwotę lub wystawcę, jeśli OCR się pomylił.",
            "Dopiero potem wykonaj właściwą czynność.",
        ]
        if priority == "normal":
            priority = "review"
    elif action:
        title = _ACTION_LABELS.get(action, action.replace("-", " ").strip().capitalize())
        reason = "DocPilot oznaczył dokument jako wymagający działania."
        steps = [title]
    elif deadline:
        title = "Pilnuj terminu"
        reason = "Dokument zawiera rozpoznany termin."
        steps = ["Zweryfikuj termin w oryginale.", "Ustaw przypomnienie lub zaplanuj wykonanie czynności."]
    else:
        title = "Zachowaj i zarchiwizuj"
        reason = "Nie wykryto pilnego terminu ani wymaganej czynności."
        steps = ["Sprawdź nazwę i kategorię.", "Zachowaj dokument w odpowiedniej sprawie."]

    if deadline and days_remaining is not None:
        if days_remaining < 0:
            reason += f" Termin minął {abs(days_remaining)} dni temu."
        elif days_remaining == 0:
            reason += " Termin przypada dzisiaj."
        else:
            reason += f" Do terminu pozostało {days_remaining} dni."

    return {
        "title": title,
        "priority": priority,
        "due_date": deadline.isoformat() if deadline else None,
        "days_remaining": days_remaining,
        "reason": reason,
        "steps": steps,
        "action_code": action or None,
    }


def proof_pack_manifest(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document.get("metadata") or {}
    digest = document.get("sha256")
    return {
        "format": "lifepilot-proof-pack",
        "version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "document": {
            "id": document.get("id"),
            "source_name": document.get("source_name"),
            "path": document.get("path"),
            "size_bytes": document.get("size_bytes"),
            "category": document.get("category"),
            "profile": document.get("profile"),
            "case_name": document.get("case_name"),
            "action_required": document.get("action_required"),
        },
        "metadata": {
            "document_type": metadata.get("document_type"),
            "issuer": metadata.get("issuer"),
            "document_date": metadata.get("document_date"),
            "deadline": metadata.get("deadline"),
            "reference": metadata.get("reference"),
            "invoice_number": metadata.get("invoice_number"),
            "amount": metadata.get("amount"),
            "currency": metadata.get("currency"),
        },
        "integrity": {
            "algorithm": "sha256",
            "digest": digest,
            "available": bool(digest),
        },
        "privacy": {
            "includes_extracted_text": False,
            "includes_file_bytes": False,
        },
    }


def build_lifepilot_view(document: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    return {
        "next_action": next_action_for_document(document, today=today),
        "proof_pack": proof_pack_manifest(document),
    }
