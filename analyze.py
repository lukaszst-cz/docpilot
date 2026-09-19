from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

from dateutil import parser as date_parser

from .extract import extract_text
from .intelligence import (
    action_required,
    detect_sensitive,
    enrich_fields,
    health_check,
    simhash64,
    suggest_case,
    tags_for,
)
from .models import ExtractedMetadata, FileAnalysis

_AMOUNT_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2}))\s?(PLN|zł|EUR|€|USD|\$)", re.I)
_REFERENCE_RE = re.compile(r"(?:nr|numer|invoice|faktura|policy|polisa|reference|ref\.?)[\s:#-]*([A-Z0-9][A-Z0-9./_-]{3,})", re.I)
_DATE_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})\b")
_DEADLINE_PHRASES = (
    "termin płatności", "płatne do", "zapłacić do", "due date", "payment due",
    "deadline", "odpowiedź do", "response by", "ważne do", "valid until",
    "obowiązuje do", "expires", "wygaśnięcie", "expiration", "przegląd do",
)

TYPE_RULES = [
    ("invoice", ("faktura", "invoice", "vat")),
    ("receipt", ("paragon", "receipt")),
    ("insurance", ("ubezpiec", "polisa", "insurance", "claim", "szkoda")),
    ("contract", ("umowa", "contract", "agreement")),
    ("warranty", ("gwarancja", "warranty")),
    ("vehicle", ("dowód rejestracyjny", "przegląd techniczny", "vehicle inspection")),
    ("school", ("szkoła", "uczeń", "nauczyciel", "librus")),
    ("official-letter", ("wezwanie", "decyzja", "postanowienie", "urząd", "court", "sąd")),
]

CATEGORY_MAP = {
    "invoice": "Finance/Invoices",
    "receipt": "Finance/Receipts",
    "insurance": "Insurance",
    "contract": "Contracts",
    "warranty": "Purchases/Warranties",
    "vehicle": "Vehicle",
    "school": "School",
    "official-letter": "Official",
    "document": "Documents",
}


def analyze_file(path: Path, custom_types: list[dict] | None = None) -> FileAnalysis:
    text, warnings = extract_text(path)
    metadata = infer_metadata(text, path.name, custom_types=custom_types)
    base = FileAnalysis(
        source_name=path.name,
        source_path=str(path.resolve()),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        extracted_text=text[:20000],
        metadata=metadata,
        suggested_category=CATEGORY_MAP.get(metadata.document_type, "Documents"),
        suggested_filename="",
        warnings=warnings,
    )
    enriched = enrich_fields(base)
    for key, value in enriched.items():
        if hasattr(metadata, key):
            setattr(metadata, key, value)
    base.suggested_filename = suggest_filename(path, metadata)
    base.tags = tags_for(base)
    base.suggested_case = suggest_case(base)
    base.action_required = action_required(base)
    base.health_score, base.health_notes = health_check(path, text, warnings)
    base.sensitive = detect_sensitive(text)
    base.simhash = simhash64(text)
    return base


def infer_metadata(text: str, filename: str = "", custom_types: list[dict] | None = None) -> ExtractedMetadata:
    haystack = f"{filename}\n{text}"
    low = haystack.lower()

    document_type = "document"
    rules = list(TYPE_RULES)
    for custom in custom_types or []:
        rules.insert(0, (custom.get("name", "document"), tuple(custom.get("keywords") or [])))
    for candidate, keywords in rules:
        if any(keyword.lower() in low for keyword in keywords if keyword):
            document_type = candidate
            break

    amount = None
    currency = None
    amount_match = _AMOUNT_RE.search(haystack)
    if amount_match:
        raw = amount_match.group(1).replace(" ", "").replace(",", ".")
        try:
            amount = float(raw)
            cur = amount_match.group(2).lower()
            currency = "PLN" if cur in {"pln", "zł"} else "EUR" if cur in {"eur", "€"} else "USD"
        except ValueError:
            pass

    reference = None
    ref_match = _REFERENCE_RE.search(haystack)
    if ref_match:
        reference = ref_match.group(1)

    dates = _extract_dates(haystack)
    document_date = dates[0] if dates else None
    deadline = _extract_deadline(haystack)

    issuer = _infer_issuer(text)
    score = 0.35
    score += 0.15 if document_type != "document" else 0
    score += 0.15 if document_date else 0
    score += 0.15 if deadline else 0
    score += 0.10 if amount is not None else 0
    score += 0.10 if issuer else 0

    return ExtractedMetadata(
        document_type=document_type,
        issuer=issuer,
        amount=amount,
        currency=currency,
        document_date=document_date,
        deadline=deadline,
        reference=reference,
        confidence=min(score, 0.95),
    )


def _extract_dates(text: str) -> list[date]:
    out: list[date] = []
    seen: set[date] = set()
    for match in _DATE_RE.findall(text):
        try:
            value = date_parser.parse(match, dayfirst=True, fuzzy=False).date()
            if date(1990, 1, 1) <= value <= date.today() + timedelta(days=3650) and value not in seen:
                out.append(value)
                seen.add(value)
        except (ValueError, OverflowError):
            continue
    return out[:30]


def _extract_deadline(text: str) -> date | None:
    low = text.lower()
    for phrase in _DEADLINE_PHRASES:
        idx = low.find(phrase)
        if idx >= 0:
            window = text[idx : idx + 220]
            dates = _extract_dates(window)
            if dates:
                return dates[0]
    return None


def _infer_issuer(text: str) -> str | None:
    for line in (ln.strip() for ln in text.splitlines()[:15]):
        if 3 <= len(line) <= 90 and any(ch.isalpha() for ch in line):
            if not _DATE_RE.search(line) and not _AMOUNT_RE.search(line):
                return line[:90]
    return None


def suggest_filename(path: Path, metadata: ExtractedMetadata) -> str:
    parts: list[str] = []
    if metadata.document_date:
        parts.append(metadata.document_date.isoformat())
    if metadata.issuer:
        parts.append(_slug(metadata.issuer, 40))
    parts.append(metadata.document_type)
    if metadata.invoice_number:
        parts.append(_slug(metadata.invoice_number, 28))
    elif metadata.reference:
        parts.append(_slug(metadata.reference, 28))
    elif metadata.amount is not None and metadata.currency:
        parts.append(f"{metadata.amount:.2f}-{metadata.currency}")
    stem = "_".join(p for p in parts if p).strip("_") or _slug(path.stem, 80)
    return f"{stem}{path.suffix.lower()}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str, limit: int) -> str:
    value = value.strip().replace("/", "-").replace("\\", "-")
    value = re.sub(r"[^\w .-]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s.]+", "-", value).strip("-_")
    return value[:limit] or "document"
