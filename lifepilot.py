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
    manual_verified = bool(metadata.get("manual_verified"))

    if confidence < 0.65 and not manual_verified:
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

    verification = {
        "source": "manual" if manual_verified else "automatic",
        "label": "Dane sprawdzone ręcznie" if manual_verified else "Automatyczny odczyt",
        "confidence": confidence,
        "verified_at": metadata.get("manual_verified_at") if manual_verified else None,
    }
    decision_basis: list[str] = [verification["label"]]
    if not manual_verified:
        decision_basis.append(f"Pewność rozpoznania: {round(confidence * 100)}%")
    if deadline:
        decision_basis.append(f"Termin: {deadline.isoformat()}")
    if action:
        decision_basis.append(f"Akcja: {action}")
    if metadata.get("document_type"):
        decision_basis.append(f"Typ: {metadata.get('document_type')}")

    return {
        "title": title,
        "priority": priority,
        "due_date": deadline.isoformat() if deadline else None,
        "days_remaining": days_remaining,
        "reason": reason,
        "steps": steps,
        "action_code": action or None,
        "verification": verification,
        "decision_basis": decision_basis,
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



def _attention_payload_v1(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document.get("metadata") or {}
    return {
        "id": document.get("id"),
        "sha256": document.get("sha256"),
        "action_required": document.get("action_required"),
        "deadline": metadata.get("deadline"),
        "warranty_until": metadata.get("warranty_until"),
        "confidence": metadata.get("confidence"),
        "case_name": document.get("case_name"),
        "category": document.get("category"),
        "profile": document.get("profile"),
        "updated_at": document.get("updated_at"),
    }


def legacy_attention_signature(document: dict[str, Any]) -> str:
    encoded = json.dumps(_attention_payload_v1(document), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def attention_signature(document: dict[str, Any]) -> str:
    metadata = document.get("metadata") or {}
    payload = {
        "version": 2,
        "id": document.get("id"),
        "sha256": document.get("sha256"),
        "action_required": document.get("action_required"),
        "case_name": document.get("case_name"),
        "category": document.get("category"),
        "profile": document.get("profile"),
        "document_type": metadata.get("document_type"),
        "issuer": metadata.get("issuer"),
        "amount": metadata.get("amount"),
        "currency": metadata.get("currency"),
        "document_date": metadata.get("document_date"),
        "deadline": metadata.get("deadline"),
        "warranty_until": metadata.get("warranty_until"),
        "confidence": metadata.get("confidence"),
        "manual_verified": metadata.get("manual_verified"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def proof_pack_preview(
    document: dict[str, Any],
    *,
    timeline_documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source = Path(str(document.get("path") or ""))
    timeline = proof_pack_timeline(timeline_documents or [document])
    source_exists = source.exists() and source.is_file()
    return {
        "document_id": document.get("id"),
        "source_name": document.get("source_name"),
        "source_available": source_exists,
        "source_size_bytes": source.stat().st_size if source_exists else None,
        "timeline_items": len(timeline),
        "case_name": document.get("case_name"),
        "files": [
            {"name": f"original/{_safe_name(source.name or document.get('source_name') or 'document')}", "kind": "original", "available": source_exists},
            {"name": "manifest.json", "kind": "metadata", "available": True},
            {"name": "next-action.json", "kind": "recommendation", "available": True},
            {"name": "timeline.json", "kind": "timeline", "available": True},
            {"name": "SHA256SUMS.txt", "kind": "integrity", "available": True},
            {"name": "README.txt", "kind": "readme", "available": True},
        ],
        "integrity": {
            "algorithm": "sha256",
            "indexed_digest_available": bool(document.get("sha256")),
            "will_verify_source_on_export": source_exists,
        },
        "privacy": {
            "includes_extracted_text": False,
            "includes_local_path_in_manifest": False,
            "uploads_anything": False,
        },
    }

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


def lifepilot_queue(
    documents: list[dict[str, Any]],
    *,
    today: date | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    today = today or date.today()
    priority_order = {"overdue": 0, "today": 1, "urgent": 2, "review": 3, "soon": 4, "normal": 5}
    items: list[dict[str, Any]] = []
    for document in documents:
        next_action = next_action_for_document(document, today=today)
        if next_action["priority"] == "normal" and not document.get("action_required") and not next_action.get("due_date"):
            continue
        items.append(
            {
                "id": document.get("id"),
                "source_name": document.get("source_name"),
                "case_name": document.get("case_name"),
                "category": document.get("category"),
                "profile": document.get("profile"),
                "action_required": document.get("action_required"),
                "next_action": next_action,
            }
        )
    items.sort(
        key=lambda item: (
            priority_order.get(item["next_action"].get("priority"), 99),
            item["next_action"].get("due_date") or "9999-12-31",
            str(item.get("source_name") or "").lower(),
            int(item.get("id") or 0),
        )
    )
    return items[: max(1, min(int(limit), 1000))]


def build_case_summary(case_name: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [doc for doc in documents if str(doc.get("case_name") or "").strip() == case_name.strip()]
    selected.sort(
        key=lambda doc: (
            str((doc.get("metadata") or {}).get("document_date") or doc.get("updated_at") or ""),
            int(doc.get("id") or 0),
        )
    )
    timeline = []
    for doc in selected:
        metadata = doc.get("metadata") or {}
        timeline.append(
            {
                "id": doc.get("id"),
                "name": doc.get("source_name"),
                "document_type": metadata.get("document_type"),
                "document_date": metadata.get("document_date"),
                "deadline": metadata.get("deadline") or metadata.get("warranty_until"),
                "issuer": metadata.get("issuer"),
                "amount": metadata.get("amount"),
                "currency": metadata.get("currency"),
                "category": doc.get("category"),
                "profile": doc.get("profile"),
                "action_required": doc.get("action_required"),
                "sha256": doc.get("sha256"),
            }
        )

    deadlines = [item["deadline"] for item in timeline if item.get("deadline")]
    actions = [item for item in timeline if item.get("action_required")]
    return {
        "format": "lifepilot-case-summary",
        "version": 1,
        "case_name": case_name.strip(),
        "document_count": len(timeline),
        "open_actions": len(actions),
        "next_deadline": min(deadlines) if deadlines else None,
        "timeline": timeline,
        "privacy": {
            "includes_extracted_text": False,
            "includes_local_paths": False,
            "uploads_anything": False,
        },
        "limitations": [
            "Daty i metadane mogą pochodzić z OCR lub ręcznej korekty i powinny być zweryfikowane z oryginałem.",
            "SHA-256 pomaga sprawdzić integralność pliku, ale nie jest kwalifikowanym znacznikiem czasu.",
        ],
    }


def case_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# LifePilot — sprawa: {summary.get('case_name') or 'Bez nazwy'}",
        "",
        f"Dokumenty: {summary.get('document_count', 0)}",
        f"Otwarte działania: {summary.get('open_actions', 0)}",
        f"Najbliższy termin: {summary.get('next_deadline') or 'brak'}",
        "",
        "## Chronologia",
        "",
    ]
    for item in summary.get("timeline") or []:
        date_value = item.get("document_date") or "brak daty"
        details = [
            str(item.get("document_type") or "document"),
            str(item.get("issuer") or "").strip(),
            str(item.get("category") or "").strip(),
        ]
        details = [value for value in details if value]
        lines.append(f"### {date_value} — {item.get('name') or 'Dokument'}")
        if details:
            lines.append("- " + " · ".join(details))
        if item.get("deadline"):
            lines.append(f"- Termin: {item['deadline']}")
        if item.get("action_required"):
            lines.append(f"- Działanie: {item['action_required']}")
        if item.get("amount") is not None:
            lines.append(f"- Kwota: {item['amount']} {item.get('currency') or ''}".rstrip())
        if item.get("sha256"):
            lines.append(f"- SHA-256: {item['sha256']}")
        lines.append("")

    lines += [
        "## Prywatność i ograniczenia",
        "",
        "- Eksport nie zawiera pełnego tekstu OCR ani lokalnych ścieżek plików.",
        "- Eksport powstaje lokalnie i sam niczego nie wysyła.",
    ]
    for limitation in summary.get("limitations") or []:
        lines.append(f"- {limitation}")
    return "\n".join(lines).rstrip() + "\n"


def build_lifepilot_view(document: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    return {
        "next_action": next_action_for_document(document, today=today),
        "proof_pack": proof_pack_manifest(document),
    }
