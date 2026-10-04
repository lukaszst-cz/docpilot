from __future__ import annotations

import hashlib
import json
import re
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


def handled_entry_matches(entry: Any, document: dict[str, Any]) -> bool:
    if isinstance(entry, str):
        return entry in {attention_signature(document), legacy_attention_signature(document)}
    if isinstance(entry, dict):
        return str(entry.get("signature") or "") == attention_signature(document)
    return False


def handled_entry_done_at(entry: Any) -> str | None:
    if isinstance(entry, dict):
        value = str(entry.get("done_at") or "").strip()
        return value or None
    return None


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


def _zip_member_sha256(archive: zipfile.ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with archive.open(name, "r") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_proof_pack(
    path: Path,
    *,
    max_total_bytes: int = 200 * 1024 * 1024,
    max_entries: int = 100,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "format": "lifepilot-proof-pack-verification",
        "version": 1,
        "valid": False,
        "checks": [],
        "errors": [],
        "warnings": [],
        "manifest": None,
        "original": None,
        "integrity": {
            "checksums_verified": False,
            "source_matches_manifest": None,
            "source_matches_index": None,
        },
    }
    if not path.exists() or not path.is_file():
        result["errors"].append("ProofPack file does not exist.")
        return result
    if not zipfile.is_zipfile(path):
        result["errors"].append("File is not a valid ZIP archive.")
        return result

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) > max_entries:
                result["errors"].append(f"Archive contains too many entries ({len(infos)} > {max_entries}).")
                return result
            if len(names) != len(set(names)):
                result["errors"].append("Archive contains duplicate filenames.")
                return result

            unsafe = [
                name for name in names
                if name.startswith(("/", "\\"))
                or re.match(r"^[A-Za-z]:", name)
                or ".." in Path(name.replace("\\", "/")).parts
            ]
            if unsafe:
                result["errors"].append("Archive contains unsafe member paths.")
                return result

            total_size = sum(max(0, int(info.file_size)) for info in infos)
            if total_size > max_total_bytes:
                result["errors"].append(
                    f"Archive expands beyond the verification limit ({total_size} > {max_total_bytes} bytes)."
                )
                return result

            required = {"manifest.json", "next-action.json", "timeline.json", "SHA256SUMS.txt", "README.txt"}
            missing = sorted(required.difference(names))
            if missing:
                result["errors"].append("Missing required files: " + ", ".join(missing))
                return result

            originals = [name for name in names if name.startswith("original/") and not name.endswith("/")]
            if len(originals) != 1:
                result["errors"].append("ProofPack must contain exactly one original document.")
                return result
            original_name = originals[0]
            result["original"] = original_name

            sums_info = archive.getinfo("SHA256SUMS.txt")
            if sums_info.file_size > 128 * 1024:
                result["errors"].append("SHA256SUMS.txt is unexpectedly large.")
                return result
            sums_text = archive.read("SHA256SUMS.txt").decode("utf-8", errors="strict")
            expected: dict[str, str] = {}
            for raw_line in sums_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                match = re.fullmatch(r"([0-9a-fA-F]{64})\s{2}(.+)", line)
                if not match:
                    result["errors"].append("SHA256SUMS.txt contains an invalid line.")
                    continue
                digest, name = match.group(1).lower(), match.group(2)
                if name in expected:
                    result["errors"].append(f"Duplicate checksum entry: {name}")
                    continue
                expected[name] = digest

            required_checked = {original_name, "manifest.json", "next-action.json", "timeline.json"}
            missing_sums = sorted(required_checked.difference(expected))
            if missing_sums:
                result["errors"].append("Missing checksum entries: " + ", ".join(missing_sums))

            for name, expected_digest in expected.items():
                if name not in names:
                    result["errors"].append(f"Checksum references missing file: {name}")
                    continue
                actual_digest = _zip_member_sha256(archive, name)
                ok = actual_digest == expected_digest
                result["checks"].append(
                    {
                        "name": name,
                        "expected_sha256": expected_digest,
                        "actual_sha256": actual_digest,
                        "ok": ok,
                    }
                )
                if not ok:
                    result["errors"].append(f"Checksum mismatch: {name}")

            result["integrity"]["checksums_verified"] = bool(expected) and not any(
                not check["ok"] for check in result["checks"]
            )

            manifest_info = archive.getinfo("manifest.json")
            if manifest_info.file_size > 2 * 1024 * 1024:
                result["errors"].append("manifest.json is unexpectedly large.")
                return result
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                result["errors"].append("manifest.json is not valid UTF-8 JSON.")
                return result
            if not isinstance(manifest, dict):
                result["errors"].append("manifest.json must contain a JSON object.")
                return result
            result["manifest"] = {
                "format": manifest.get("format"),
                "version": manifest.get("version"),
                "generated_at": manifest.get("generated_at"),
                "source_name": (manifest.get("document") or {}).get("source_name"),
                "document_type": (manifest.get("metadata") or {}).get("document_type"),
                "case_name": (manifest.get("document") or {}).get("case_name"),
            }
            if manifest.get("format") != "lifepilot-proof-pack":
                result["errors"].append("Unexpected ProofPack manifest format.")
            if manifest.get("version") != 1:
                result["warnings"].append(f"Manifest version {manifest.get('version')} is not the expected v1.")

            original_digest = next(
                (check["actual_sha256"] for check in result["checks"] if check["name"] == original_name and check["ok"]),
                None,
            )
            integrity = manifest.get("integrity") if isinstance(manifest.get("integrity"), dict) else {}
            manifest_computed = str(integrity.get("computed_digest") or "").lower() or None
            indexed_digest = str(integrity.get("digest") or "").lower() or None
            if original_digest and manifest_computed:
                source_matches_manifest = original_digest == manifest_computed
                result["integrity"]["source_matches_manifest"] = source_matches_manifest
                if not source_matches_manifest:
                    result["errors"].append("Original document does not match manifest computed_digest.")
            elif not manifest_computed:
                result["warnings"].append("Manifest does not contain computed_digest.")

            if original_digest and indexed_digest:
                source_matches_index = original_digest == indexed_digest
                result["integrity"]["source_matches_index"] = source_matches_index
                if not source_matches_index:
                    result["warnings"].append(
                        "Original is internally valid but differs from the SHA-256 recorded in the document index."
                    )
            elif not indexed_digest:
                result["warnings"].append("Manifest does not contain the indexed SHA-256 digest.")

    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        result["errors"].append(f"Could not verify ProofPack: {exc}")

    result["valid"] = not result["errors"]
    return result


def _case_documents(case_name: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    name = case_name.strip()
    selected = [doc for doc in documents if str(doc.get("case_name") or "").strip() == name]
    selected.sort(
        key=lambda doc: (
            str((doc.get("metadata") or {}).get("document_date") or doc.get("updated_at") or ""),
            int(doc.get("id") or 0),
        )
    )
    return selected


def case_readiness(
    case_name: str,
    documents: list[dict[str, Any]],
    *,
    today: date | None = None,
    verify_integrity: bool = True,
) -> dict[str, Any]:
    today = today or date.today()
    selected = _case_documents(case_name, documents)
    issues: list[dict[str, Any]] = []
    counts = {
        "missing_originals": 0,
        "low_confidence_unverified": 0,
        "missing_integrity": 0,
        "integrity_mismatch": 0,
        "integrity_verified": 0,
        "manual_verified": 0,
        "overdue": 0,
        "due_soon": 0,
        "open_actions": 0,
    }

    for document in selected:
        doc_id = document.get("id")
        source_name = document.get("source_name") or "Dokument"
        metadata = document.get("metadata") or {}
        source = Path(str(document.get("path") or ""))
        try:
            source_exists = source.exists() and source.is_file()
        except OSError:
            source_exists = False

        if not source_exists:
            counts["missing_originals"] += 1
            issues.append(
                {
                    "code": "missing-original",
                    "severity": "blocking",
                    "document_id": doc_id,
                    "source_name": source_name,
                    "title": "Brakuje lokalnego oryginału",
                    "detail": "Dokument jest w indeksie, ale plik źródłowy nie jest dostępny.",
                }
            )

        confidence = float(metadata.get("confidence") or 0)
        manual_verified = bool(metadata.get("manual_verified"))
        if manual_verified:
            counts["manual_verified"] += 1
        if confidence < 0.65 and not manual_verified:
            counts["low_confidence_unverified"] += 1
            issues.append(
                {
                    "code": "low-confidence-unverified",
                    "severity": "review",
                    "document_id": doc_id,
                    "source_name": source_name,
                    "title": "Dane wymagają ręcznego sprawdzenia",
                    "detail": f"Automatyczne rozpoznanie ma {round(confidence * 100)}% pewności.",
                }
            )

        indexed_digest = str(document.get("sha256") or "").lower().strip()
        if not indexed_digest:
            counts["missing_integrity"] += 1
            issues.append(
                {
                    "code": "missing-sha256",
                    "severity": "review",
                    "document_id": doc_id,
                    "source_name": source_name,
                    "title": "Brak zapisanej sumy SHA-256",
                    "detail": "Integralność pliku nie może zostać porównana z wcześniejszym indeksem.",
                }
            )
        elif source_exists and verify_integrity:
            try:
                current_digest = _sha256_file(source).lower()
            except OSError:
                current_digest = None
            if current_digest is None:
                if not any(
                    issue["code"] == "missing-original" and issue["document_id"] == doc_id
                    for issue in issues
                ):
                    counts["missing_originals"] += 1
                    issues.append(
                        {
                            "code": "missing-original",
                            "severity": "blocking",
                            "document_id": doc_id,
                            "source_name": source_name,
                            "title": "Oryginał stał się niedostępny",
                            "detail": "Plik zniknął lub stał się niedostępny podczas kontroli integralności.",
                        }
                    )
            elif current_digest == indexed_digest:
                counts["integrity_verified"] += 1
            else:
                counts["integrity_mismatch"] += 1
                issues.append(
                    {
                        "code": "integrity-mismatch",
                        "severity": "review",
                        "document_id": doc_id,
                        "source_name": source_name,
                        "title": "Plik różni się od wersji zindeksowanej",
                        "detail": "Aktualny SHA-256 nie zgadza się z hashem zapisanym wcześniej w DocPilot.",
                    }
                )

        next_action = next_action_for_document(document, today=today)
        if document.get("action_required") and document.get("action_required") != "to-archive":
            counts["open_actions"] += 1
        if next_action.get("priority") == "overdue":
            counts["overdue"] += 1
            issues.append(
                {
                    "code": "overdue-action",
                    "severity": "attention",
                    "document_id": doc_id,
                    "source_name": source_name,
                    "title": "Termin minął",
                    "detail": next_action.get("reason") or "Dokument ma przeterminowany termin.",
                }
            )
        elif next_action.get("priority") in {"today", "urgent", "soon"}:
            counts["due_soon"] += 1

    if counts["missing_originals"]:
        status = "incomplete"
        label = "Niekompletna"
        recommendation = "Uzupełnij brakujące oryginały albo świadomie eksportuj CasePack z jawną informacją o brakach."
    elif counts["low_confidence_unverified"] or counts["missing_integrity"] or counts["integrity_mismatch"]:
        status = "review"
        label = "Wymaga sprawdzenia"
        recommendation = "Sprawdź wskazane dokumenty przed potraktowaniem CasePack jako uporządkowanego materiału."
    else:
        status = "ready"
        label = "Gotowa"
        recommendation = "Warstwa kompletności i integralności nie wykryła problemów blokujących przegląd sprawy."

    return {
        "format": "lifepilot-case-readiness",
        "version": 1,
        "case_name": case_name.strip(),
        "document_count": len(selected),
        "status": status,
        "label": label,
        "can_export": bool(selected),
        "counts": counts,
        "issues": issues,
        "recommendation": recommendation,
        "privacy": {
            "includes_extracted_text": False,
            "includes_local_paths": False,
            "uploads_anything": False,
        },
        "limitations": [
            "Gotowość dotyczy kompletności i integralności materiału, nie oceny prawnej lub merytorycznej sprawy.",
            "Otwarte działania i terminy są informacyjne i same nie blokują eksportu CasePack.",
        ],
    }


def case_pack_preview(case_name: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    selected = _case_documents(case_name, documents)
    items = []
    available = 0
    missing = 0
    total_bytes = 0
    for index, document in enumerate(selected, start=1):
        source = Path(str(document.get("path") or ""))
        try:
            exists = source.exists() and source.is_file()
            size = source.stat().st_size if exists else None
        except OSError:
            exists = False
            size = None
        if exists:
            available += 1
            total_bytes += int(size or 0)
        else:
            missing += 1
        items.append(
            {
                "id": document.get("id"),
                "name": document.get("source_name"),
                "available": exists,
                "size_bytes": size,
                "archive_name": (
                    f"documents/{index:03d}-{_safe_name(source.name or document.get('source_name') or 'document')}"
                    if exists
                    else None
                ),
            }
        )
    return {
        "format": "lifepilot-case-pack-preview",
        "version": 1,
        "case_name": case_name.strip(),
        "document_count": len(selected),
        "available_originals": available,
        "missing_originals": missing,
        "total_original_bytes": total_bytes,
        "documents": items,
        "privacy": {
            "includes_extracted_text": False,
            "includes_local_paths": False,
            "uploads_anything": False,
        },
    }


def build_case_pack(destination: Path, case_name: str, documents: list[dict[str, Any]]) -> Path:
    selected = _case_documents(case_name, documents)
    if not selected:
        raise ValueError("Case contains no documents.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    timeline = proof_pack_timeline(selected)
    summary = build_case_summary(case_name, selected)
    timeline_bytes = json.dumps(timeline, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    summary_bytes = case_summary_markdown(summary).encode("utf-8")

    document_entries: list[dict[str, Any]] = []
    document_files: list[tuple[Path, str, str]] = []
    manifest_files: list[tuple[str, bytes]] = []
    missing_originals: list[dict[str, Any]] = []

    for index, document in enumerate(selected, start=1):
        source = Path(str(document.get("path") or ""))
        try:
            source_exists = source.exists() and source.is_file()
            computed_digest = _sha256_file(source) if source_exists else None
        except OSError:
            source_exists = False
            computed_digest = None
        archive_name = (
            f"documents/{index:03d}-{_safe_name(source.name or document.get('source_name') or 'document')}"
            if source_exists
            else None
        )
        manifest_name = f"manifests/{index:03d}-{int(document.get('id') or 0)}.json"
        per_document_manifest = proof_pack_manifest(document, computed_digest=computed_digest)
        per_document_bytes = json.dumps(
            per_document_manifest,
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode("utf-8")
        manifest_files.append((manifest_name, per_document_bytes))

        indexed_digest = str(document.get("sha256") or "").lower() or None
        matches_index = (
            bool(indexed_digest and computed_digest)
            and indexed_digest == str(computed_digest).lower()
            if computed_digest
            else None
        )
        entry = {
            "id": document.get("id"),
            "source_name": document.get("source_name"),
            "document_type": (document.get("metadata") or {}).get("document_type"),
            "document_date": (document.get("metadata") or {}).get("document_date"),
            "deadline": (document.get("metadata") or {}).get("deadline")
            or (document.get("metadata") or {}).get("warranty_until"),
            "action_required": document.get("action_required"),
            "category": document.get("category"),
            "profile": document.get("profile"),
            "source_available": source_exists,
            "archive_name": archive_name,
            "manifest_name": manifest_name,
            "indexed_sha256": indexed_digest,
            "computed_sha256": computed_digest,
            "matches_index": matches_index,
        }
        document_entries.append(entry)
        if source_exists and archive_name and computed_digest:
            document_files.append((source, archive_name, computed_digest))
        else:
            missing_originals.append(
                {"id": document.get("id"), "source_name": document.get("source_name")}
            )

    case_manifest = {
        "format": "lifepilot-case-pack",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_name": case_name.strip(),
        "document_count": len(selected),
        "available_originals": len(document_files),
        "missing_originals": missing_originals,
        "documents": document_entries,
        "privacy": {
            "includes_extracted_text": False,
            "includes_local_paths": False,
            "uploads_anything": False,
        },
        "limitations": [
            "CasePack preserves a local evidence set but is not a qualified electronic signature or trusted timestamp.",
            "Missing originals are listed in the manifest and are not silently omitted.",
        ],
    }
    case_manifest_bytes = json.dumps(
        case_manifest,
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8")
    readme = (
        "LifePilot CasePack v1\n"
        "=====================\n\n"
        "CasePack contains the available originals for one case, per-document manifests,\n"
        "the ordered timeline, a safe case summary and SHA-256 checksums.\n\n"
        "Missing originals are listed in case-manifest.json instead of being silently ignored.\n"
        "The pack is local-first and does not include full OCR text or local file paths.\n"
        "It is not a qualified electronic signature, seal or trusted timestamp.\n"
    ).encode("utf-8")

    checksums = [
        f"{_sha256_bytes(case_manifest_bytes)}  case-manifest.json",
        f"{_sha256_bytes(timeline_bytes)}  timeline.json",
        f"{_sha256_bytes(summary_bytes)}  case-summary.md",
        f"{_sha256_bytes(readme)}  README.txt",
    ]
    for manifest_name, manifest_bytes in manifest_files:
        checksums.append(f"{_sha256_bytes(manifest_bytes)}  {manifest_name}")
    for _, archive_name, digest in document_files:
        checksums.append(f"{digest}  {archive_name}")

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, archive_name, _ in document_files:
            archive.write(source, archive_name)
        for manifest_name, manifest_bytes in manifest_files:
            archive.writestr(manifest_name, manifest_bytes)
        archive.writestr("case-manifest.json", case_manifest_bytes)
        archive.writestr("timeline.json", timeline_bytes)
        archive.writestr("case-summary.md", summary_bytes)
        archive.writestr("README.txt", readme)
        archive.writestr("SHA256SUMS.txt", "\n".join(checksums) + "\n")
    return destination


def verify_case_pack(
    path: Path,
    *,
    max_total_bytes: int = 1024 * 1024 * 1024,
    max_entries: int = 5000,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "format": "lifepilot-case-pack-verification",
        "version": 1,
        "valid": False,
        "checks": [],
        "errors": [],
        "warnings": [],
        "manifest": None,
        "integrity": {
            "checksums_verified": False,
            "documents_verified": 0,
            "documents_matching_index": 0,
            "documents_index_mismatch": 0,
            "missing_originals": 0,
        },
    }
    if not path.exists() or not path.is_file():
        result["errors"].append("CasePack file does not exist.")
        return result
    if not zipfile.is_zipfile(path):
        result["errors"].append("File is not a valid ZIP archive.")
        return result

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) > max_entries:
                result["errors"].append(f"Archive contains too many entries ({len(infos)} > {max_entries}).")
                return result
            if len(names) != len(set(names)):
                result["errors"].append("Archive contains duplicate filenames.")
                return result
            unsafe = [
                name for name in names
                if name.startswith(("/", "\\"))
                or re.match(r"^[A-Za-z]:", name)
                or ".." in Path(name.replace("\\", "/")).parts
            ]
            if unsafe:
                result["errors"].append("Archive contains unsafe member paths.")
                return result
            total_size = sum(max(0, int(info.file_size)) for info in infos)
            if total_size > max_total_bytes:
                result["errors"].append(
                    f"Archive expands beyond the verification limit ({total_size} > {max_total_bytes} bytes)."
                )
                return result

            required = {"case-manifest.json", "timeline.json", "case-summary.md", "SHA256SUMS.txt", "README.txt"}
            missing = sorted(required.difference(names))
            if missing:
                result["errors"].append("Missing required files: " + ", ".join(missing))
                return result

            try:
                manifest = json.loads(archive.read("case-manifest.json"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                result["errors"].append("case-manifest.json is not valid UTF-8 JSON.")
                return result
            if not isinstance(manifest, dict):
                result["errors"].append("case-manifest.json must contain a JSON object.")
                return result
            if manifest.get("format") != "lifepilot-case-pack":
                result["errors"].append("Unexpected CasePack manifest format.")
            if manifest.get("version") != 1:
                result["warnings"].append(f"Manifest version {manifest.get('version')} is not the expected v1.")

            documents = manifest.get("documents") if isinstance(manifest.get("documents"), list) else []
            result["manifest"] = {
                "format": manifest.get("format"),
                "version": manifest.get("version"),
                "generated_at": manifest.get("generated_at"),
                "case_name": manifest.get("case_name"),
                "document_count": manifest.get("document_count"),
                "available_originals": manifest.get("available_originals"),
                "missing_originals": len(manifest.get("missing_originals") or []),
            }

            sums_info = archive.getinfo("SHA256SUMS.txt")
            if sums_info.file_size > 2 * 1024 * 1024:
                result["errors"].append("SHA256SUMS.txt is unexpectedly large.")
                return result
            try:
                sums_text = archive.read("SHA256SUMS.txt").decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                result["errors"].append("SHA256SUMS.txt is not valid UTF-8.")
                return result

            expected: dict[str, str] = {}
            for raw_line in sums_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                match = re.fullmatch(r"([0-9a-fA-F]{64})\s{2}(.+)", line)
                if not match:
                    result["errors"].append("SHA256SUMS.txt contains an invalid line.")
                    continue
                digest, name = match.group(1).lower(), match.group(2)
                if name in expected:
                    result["errors"].append(f"Duplicate checksum entry: {name}")
                    continue
                expected[name] = digest

            baseline = {"case-manifest.json", "timeline.json", "case-summary.md", "README.txt"}
            missing_baseline = sorted(baseline.difference(expected))
            if missing_baseline:
                result["errors"].append("Missing checksum entries: " + ", ".join(missing_baseline))

            actual_digests: dict[str, str] = {}
            for name, expected_digest in expected.items():
                if name not in names:
                    result["errors"].append(f"Checksum references missing file: {name}")
                    continue
                actual_digest = _zip_member_sha256(archive, name)
                actual_digests[name] = actual_digest
                ok = actual_digest == expected_digest
                result["checks"].append(
                    {
                        "name": name,
                        "expected_sha256": expected_digest,
                        "actual_sha256": actual_digest,
                        "ok": ok,
                    }
                )
                if not ok:
                    result["errors"].append(f"Checksum mismatch: {name}")
            result["integrity"]["checksums_verified"] = bool(expected) and not any(
                not check["ok"] for check in result["checks"]
            )

            seen_archive_names: set[str] = set()
            for item in documents:
                if not isinstance(item, dict):
                    result["errors"].append("Case manifest contains an invalid document entry.")
                    continue
                manifest_name = str(item.get("manifest_name") or "")
                if not manifest_name or manifest_name not in names:
                    result["errors"].append(
                        f"Missing per-document manifest for document {item.get('id')}."
                    )
                if manifest_name and manifest_name not in expected:
                    result["errors"].append(f"Missing checksum entry: {manifest_name}")

                if not item.get("source_available"):
                    result["integrity"]["missing_originals"] += 1
                    continue

                archive_name = str(item.get("archive_name") or "")
                if not archive_name or archive_name not in names:
                    result["errors"].append(f"Missing original for document {item.get('id')}.")
                    continue
                if archive_name in seen_archive_names:
                    result["errors"].append(f"Duplicate original reference: {archive_name}")
                    continue
                seen_archive_names.add(archive_name)
                if archive_name not in expected:
                    result["errors"].append(f"Missing checksum entry: {archive_name}")
                    continue

                actual_digest = actual_digests.get(archive_name)
                if not actual_digest:
                    actual_digest = _zip_member_sha256(archive, archive_name)
                computed_digest = str(item.get("computed_sha256") or "").lower() or None
                indexed_digest = str(item.get("indexed_sha256") or "").lower() or None
                if computed_digest and actual_digest != computed_digest:
                    result["errors"].append(
                        f"Original does not match CasePack manifest for document {item.get('id')}."
                    )
                    continue

                result["integrity"]["documents_verified"] += 1
                if indexed_digest:
                    if actual_digest == indexed_digest:
                        result["integrity"]["documents_matching_index"] += 1
                    else:
                        result["integrity"]["documents_index_mismatch"] += 1
                        result["warnings"].append(
                            f"Document {item.get('id')} is internally valid but differs from its indexed SHA-256."
                        )

            declared_count = int(manifest.get("document_count") or 0)
            if declared_count != len(documents):
                result["errors"].append(
                    f"Manifest document_count ({declared_count}) does not match document entries ({len(documents)})."
                )

            referenced_originals = {
                str(item.get("archive_name"))
                for item in documents
                if isinstance(item, dict) and item.get("source_available") and item.get("archive_name")
            }
            referenced_manifests = {
                str(item.get("manifest_name"))
                for item in documents
                if isinstance(item, dict) and item.get("manifest_name")
            }
            actual_originals = {
                name for name in names if name.startswith("documents/") and not name.endswith("/")
            }
            actual_manifests = {
                name for name in names if name.startswith("manifests/") and not name.endswith("/")
            }
            extra_originals = sorted(actual_originals.difference(referenced_originals))
            extra_manifests = sorted(actual_manifests.difference(referenced_manifests))
            if extra_originals:
                result["errors"].append(
                    "CasePack contains unreferenced originals: " + ", ".join(extra_originals)
                )
            if extra_manifests:
                result["errors"].append(
                    "CasePack contains unreferenced document manifests: " + ", ".join(extra_manifests)
                )
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        result["errors"].append(f"Could not verify CasePack: {exc}")

    result["valid"] = not result["errors"]
    return result


def verify_lifepilot_pack(
    path: Path,
    *,
    proof_max_total_bytes: int = 200 * 1024 * 1024,
    case_max_total_bytes: int = 1024 * 1024 * 1024,
) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or not zipfile.is_zipfile(path):
        result = verify_proof_pack(path, max_total_bytes=proof_max_total_bytes)
        result["pack_type"] = "proofpack"
        return result
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        result = verify_proof_pack(path, max_total_bytes=proof_max_total_bytes)
        result["pack_type"] = "proofpack"
        return result
    if "case-manifest.json" in names:
        result = verify_case_pack(path, max_total_bytes=case_max_total_bytes)
        result["pack_type"] = "casepack"
        return result
    result = verify_proof_pack(path, max_total_bytes=proof_max_total_bytes)
    result["pack_type"] = "proofpack"
    return result


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
    selected = _case_documents(case_name, documents)
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
