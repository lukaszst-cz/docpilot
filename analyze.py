from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from pathlib import Path


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
_REFERENCE_PATTERNS = (
    re.compile(r"(?:nr|numer)\s+(?:umowy|sprawy|dokumentu|faktury|polisy|szkody)\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{3,})", re.I),
    re.compile(r"(?:sprawa|szkoda)\s*(?:nr)?\s*[:#-]\s*([A-Z0-9][A-Z0-9./_-]{3,})", re.I),
    re.compile(r"(?:faktura(?:\s+vat)?|invoice|policy|polisa)\s*(?:nr|no\.?|number)\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{3,})", re.I),
    re.compile(r"(?:nr|numer|reference|ref\.?)\s*[:#-]\s*([A-Z0-9][A-Z0-9./_-]{3,})", re.I),
)
_DATE_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})\b")
_DOCUMENT_DATE_RE = re.compile(
    r"(?:data(?:\s+(?:wystawienia|pisma|zawarcia|zakupu|kosztorysu|dokumentu|sporządzenia|sporzadzenia))?|zawarta\s+dnia|sporządzono\s+dnia|sporzadzono\s+dnia)"
    r"\s*[:#-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})",
    re.I,
)
_RELATIVE_DEADLINE_RE = re.compile(
    r"\b(?:w\s+terminie\s+|w\s+ciągu\s+|w\s+ciagu\s+)?(\d{1,3})\s+dni\s+od\s+(?:(?:dnia|daty)\s+)?(?:doręczenia|doreczenia)\b",
    re.I,
)
_DELIVERY_DATE_RE = re.compile(
    r"(?:data\s+)?(?:doręczenia|doreczenia)\s*[:#-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})",
    re.I,
)
_EXPLICIT_DO_DATE_RE = re.compile(
    r"\bdo\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})\b",
    re.I,
)
_ISSUER_LABEL_RE = re.compile(
    r"^(?:wystawca|sprzedawca|nadawca|ubezpieczyciel|firma)\s*:\s*(.+)$",
    re.I,
)
_ISSUER_ORG_RE = re.compile(
    r"\b(?:sp\.?\s*z\s*o\.?o\.?|s\.?\s*a\.?|urząd|urzad|szkoł|sklep|bank|towarzystwo|fundacja|spółdzielnia|spoldzielnia)\b",
    re.I,
)
_DEADLINE_PHRASES = (
    "termin płatności", "termin platnosci", "płatne do", "platne do", "zapłacić do", "zaplacic do",
    "due date", "payment due", "deadline", "odpowiedź do", "odpowiedz do", "response by",
    "ważne do", "wazne do", "valid until", "obowiązuje do", "obowiazuje do", "expires",
    "wygaśnięcie", "wygasniecie", "expiration", "przegląd do", "przeglad do",
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
    if enriched.get("gross_amount") is not None:
        metadata.amount = enriched["gross_amount"]
    base.suggested_filename = suggest_filename(path, metadata)
    base.tags = tags_for(base)
    base.suggested_case = suggest_case(base)
    base.action_required = action_required(base)
    base.health_score, base.health_notes = health_check(path, text, warnings)
    if warnings and base.health_score <= 80:
        metadata.confidence = min(metadata.confidence, 0.60)
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

    reference = _extract_reference(text)

    document_date = _extract_document_date(text)
    if document_date is None:
        dates = _extract_dates(text)
        document_date = dates[0] if len(dates) == 1 else None
    deadline = _extract_deadline(text)

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


def _parse_numeric_date(value: str) -> date | None:
    parts = re.split(r"[./-]", value)
    if len(parts) != 3:
        return None
    try:
        if len(parts[0]) == 4:
            year, month, day = (int(part) for part in parts)
        else:
            day, month, year = (int(part) for part in parts)
            if year < 100:
                year += 2000 if year < 70 else 1900
        return date(year, month, day)
    except ValueError:
        return None


def _extract_dates(text: str) -> list[date]:
    out: list[date] = []
    seen: set[date] = set()
    for match in _DATE_RE.findall(text):
        value = _parse_numeric_date(match)
        if value and date(1990, 1, 1) <= value <= date.today() + timedelta(days=3650) and value not in seen:
            out.append(value)
            seen.add(value)
    return out[:30]


def _extract_document_date(text: str) -> date | None:
    match = _DOCUMENT_DATE_RE.search(text)
    return _parse_numeric_date(match.group(1)) if match else None


def _extract_reference(text: str) -> str | None:
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _extract_deadline(text: str) -> date | None:
    relative = _RELATIVE_DEADLINE_RE.search(text)
    if relative:
        delivered = _DELIVERY_DATE_RE.search(text)
        delivered_date = _parse_numeric_date(delivered.group(1)) if delivered else None
        if delivered_date:
            return delivered_date + timedelta(days=int(relative.group(1)))

    low = text.lower()
    for phrase in _DEADLINE_PHRASES:
        idx = low.find(phrase)
        if idx >= 0:
            window = text[idx : idx + 220]
            dates = _extract_dates(window)
            if dates:
                return dates[0]

    explicit = _EXPLICIT_DO_DATE_RE.search(text)
    return _parse_numeric_date(explicit.group(1)) if explicit else None


def _infer_issuer(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines()[:20] if ln.strip()]
    for line in lines:
        match = _ISSUER_LABEL_RE.match(line)
        if match:
            value = match.group(1).strip()
            if 2 <= len(value) <= 90:
                return value[:90]

    for line in lines:
        if line.startswith("[PAGE "):
            continue
        if _DATE_RE.search(line) or _AMOUNT_RE.search(line):
            continue
        if _ISSUER_ORG_RE.search(line):
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
