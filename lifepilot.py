from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


_ACTION_LABELS = {
    "to-pay": "Zweryfikuj i opłać dokument",
    "to-reply": "Przygotuj odpowiedź",
    "to-sign": "Sprawdź i podpisz dokument",
    "to-review": "Sprawdź dokument ręcznie",
    "to-renew": "Sprawdź odnowienie lub przedłużenie",
    "to-archive": "Zatwierdź i zachowaj dokument",
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
        "available_actions": {
            "proof_pack": True,
            "calendar": bool(deadline),
            "open_source": bool(document.get("path")),
            "scam_check": True,
        },
    }


def proof_pack_manifest(document: dict[str, Any], *, computed_digest: str | None = None) -> dict[str, Any]:
    metadata = document.get("metadata") or {}
    indexed_digest = document.get("sha256")
    return {
        "format": "lifepilot-proof-pack",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document": {
            "id": document.get("id"),
            "source_name": document.get("source_name"),
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
            "digest": indexed_digest,
            "computed_digest": computed_digest,
            "matches_index": (
                bool(indexed_digest and computed_digest) and str(indexed_digest).lower() == str(computed_digest).lower()
                if computed_digest
                else None
            ),
            "available": bool(indexed_digest),
        },
        "privacy": {
            "includes_extracted_text": False,
            "includes_local_path": False,
        },
    }


def _safe_name(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(value))
    return cleaned[:120] or "document"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def proof_pack_timeline(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for document in documents:
        metadata = document.get("metadata") or {}
        items.append(
            {
                "id": document.get("id"),
                "source_name": document.get("source_name"),
                "sha256": document.get("sha256"),
                "document_type": metadata.get("document_type"),
                "document_date": metadata.get("document_date"),
                "deadline": metadata.get("deadline") or metadata.get("warranty_until"),
                "case_name": document.get("case_name"),
                "category": document.get("category"),
                "action_required": document.get("action_required"),
            }
        )
    return items


def build_proof_pack(
    destination: Path,
    document: dict[str, Any],
    *,
    timeline_documents: list[dict[str, Any]] | None = None,
) -> Path:
    source = Path(str(document.get("path") or ""))
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Source document not found: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_digest = _sha256_file(source)
    manifest = proof_pack_manifest(document, computed_digest=source_digest)
    next_action = next_action_for_document(document)
    timeline = proof_pack_timeline(timeline_documents or [document])

    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    action_bytes = json.dumps(next_action, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    timeline_bytes = json.dumps(timeline, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    original_arcname = f"original/{_safe_name(source.name)}"

    checksums = [
        f"{source_digest}  {original_arcname}",
        f"{_sha256_bytes(manifest_bytes)}  manifest.json",
        f"{_sha256_bytes(action_bytes)}  next-action.json",
        f"{_sha256_bytes(timeline_bytes)}  timeline.json",
    ]
    readme = (
        "LifePilot ProofPack v1\n"
        "======================\n\n"
        "Pakiet utworzono lokalnie na podstawie dokumentu zindeksowanego w DocPilot/LifePilot.\n"
        "Zawiera kopię dokumentu, manifest metadanych, rekomendowaną następną czynność,\n"
        "chronologię sprawy (jeśli była dostępna) oraz sumy SHA-256.\n\n"
        "ProofPack pomaga zachować spójny zestaw materiałów, ale nie jest kwalifikowanym\n"
        "podpisem elektronicznym, kwalifikowaną pieczęcią ani zaufanym znacznikiem czasu.\n"
        "Dla ważnych spraw zawsze zachowaj oryginały i zweryfikuj kluczowe dane.\n"
    )

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, original_arcname)
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("next-action.json", action_bytes)
        archive.writestr("timeline.json", timeline_bytes)
        archive.writestr("SHA256SUMS.txt", "\n".join(checksums) + "\n")
        archive.writestr("README.txt", readme)
    return destination


def build_lifepilot_view(document: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    return {
        "next_action": next_action_for_document(document, today=today),
        "proof_pack": proof_pack_manifest(document),
    }
