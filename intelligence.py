from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .models import ExtractedMetadata, FileAnalysis

SYNONYMS = {
    "zalanie": ["szkoda", "woda", "ubezpieczenie", "wyciek"],
    "faktura": ["invoice", "rachunek", "vat", "płatność"],
    "umowa": ["contract", "agreement", "wypowiedzenie"],
    "samochód": ["pojazd", "auto", "rejestracja", "polisa", "oc"],
    "szkoła": ["uczeń", "nauczyciel", "librus", "edukacja"],
    "ubezpieczenie": ["polisa", "claim", "szkoda", "ubezpieczyciel"],
    "termin": ["deadline", "due", "ważne do", "odpowiedź do"],
}

PESEL_RE = re.compile(r"\b\d{11}\b")
NIP_RE = re.compile(r"\b(?:PL)?\s?\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}\b", re.I)
IBAN_RE = re.compile(r"\bPL\s?(?:\d[ -]?){26}\b", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+48[ -]?)?(?:\d[ -]?){9}(?!\d)")
ADDRESS_RE = re.compile(r"\b(?:ul\.|ulica|al\.|aleja|os\.|osiedle)\s+[A-ZĄĆĘŁŃÓŚŹŻ][^\n,]{2,50}\s+\d+[A-Za-z]?", re.I)
BANK_RE = re.compile(r"\b(?:rachunek|konto|account|iban)\b", re.I)
VAT_RE = re.compile(r"\bVAT\s*(\d{1,2}(?:[,.]\d{1,2})?)\s*%", re.I)
NET_RE = re.compile(r"(?:netto|net)\D{0,20}(\d[\d .]*[,.]\d{2})", re.I)
GROSS_RE = re.compile(r"(?:brutto|gross|do zapłaty|razem)\D{0,20}(\d[\d .]*[,.]\d{2})", re.I)
INVOICE_NO_RE = re.compile(r"(?:faktura|invoice)\s*(?:nr|no\.?|number)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})", re.I)
NOTICE_RE = re.compile(r"(?:okres wypowiedzenia|notice period)\D{0,20}(\d+)\s*(dni|days|miesiąc|miesiące|months)", re.I)
WARRANTY_RE = re.compile(r"(?:gwarancj\w*|warranty)\D{0,30}(\d+)\s*(miesięcy|miesiące|months|lat|years)", re.I)
AUTO_RENEW_RE = re.compile(r"(?:automatyczn\w* przedłuż|automatic renewal|renews automatically)", re.I)


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[\wąćęłńóśźż-]{3,}", text, re.I)]


def simhash64(text: str) -> str:
    words = tokenize(text)
    if not words:
        return "0" * 16
    counts = Counter(words[:6000])
    vector = [0] * 64
    for token, weight in counts.items():
        digest = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += weight if (digest >> bit) & 1 else -weight
    value = 0
    for bit, score in enumerate(vector):
        if score >= 0:
            value |= 1 << bit
    return f"{value:016x}"


def hamming_hex(a: str | None, b: str | None) -> int:
    if not a or not b:
        return 64
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except ValueError:
        return 64


def language_detect(text: str) -> str:
    low = text.lower()
    scores = {
        "pl": sum(low.count(w) for w in (" oraz ", " dnia ", " faktura", " umowa", " termin", " kwota", " płat")),
        "en": sum(low.count(w) for w in (" the ", " and ", " invoice", " agreement", " due ", " amount")),
        "de": sum(low.count(w) for w in (" der ", " die ", " und ", " rechnung", " vertrag", " betrag")),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def detect_sensitive(text: str) -> list[dict[str, str]]:
    patterns = [
        ("PESEL", PESEL_RE), ("NIP", NIP_RE), ("IBAN", IBAN_RE),
        ("email", EMAIL_RE), ("phone", PHONE_RE), ("address", ADDRESS_RE),
    ]
    found: list[dict[str, str]] = []
    seen = set()
    for kind, regex in patterns:
        for m in regex.finditer(text):
            value = m.group(0).strip()
            key = (kind, value)
            if key not in seen:
                seen.add(key)
                found.append({"type": kind, "value": value})
    return found[:100]


def redact_text(text: str) -> tuple[str, list[dict[str, str]]]:
    found = detect_sensitive(text)
    redacted = text
    for item in sorted(found, key=lambda x: len(x["value"]), reverse=True):
        redacted = redacted.replace(item["value"], f"[REDACTED {item['type']}]")
    return redacted, found


def tags_for(analysis: FileAnalysis) -> list[str]:
    md = analysis.metadata
    tags = {md.document_type, language_detect(analysis.extracted_text)}
    low = analysis.extracted_text.lower()
    mapping = {
        "finance": ("faktura", "invoice", "paragon", "rachunek", "vat"),
        "insurance": ("polisa", "ubezpiec", "claim", "szkoda"),
        "school": ("szkoła", "uczeń", "nauczyciel", "librus"),
        "vehicle": ("pojazd", "samochód", "rejestrac", "oc", "ac"),
        "legal": ("sąd", "pozew", "decyzja", "wezwanie", "urząd"),
        "important": ("pilne", "termin", "deadline", "wezwanie", "ostateczny"),
    }
    for tag, keywords in mapping.items():
        if any(k in low for k in keywords):
            tags.add(tag)
    return sorted(t for t in tags if t and t != "unknown")


def action_required(analysis: FileAnalysis) -> str | None:
    text = analysis.extracted_text.lower()
    md = analysis.metadata
    if md.deadline:
        if md.document_type == "invoice" or any(k in text for k in ("do zapłaty", "termin płatności", "payment due")):
            return "to-pay"
        if any(k in text for k in ("odpowiedź", "response", "ustosunk", "wyjaśn")):
            return "to-reply"
        return "to-review"
    if any(k in text for k in ("podpis", "signature", "sign here")):
        return "to-sign"
    if md.document_type in {"receipt", "document"}:
        return "to-archive"
    return None


def suggest_case(analysis: FileAnalysis) -> str | None:
    md = analysis.metadata
    if md.reference:
        prefix = md.issuer or md.document_type
        return f"{prefix} — {md.reference}"[:120]
    low = analysis.extracted_text.lower()
    if md.document_type == "insurance" and "szkoda" in low:
        return f"Insurance case — {md.issuer or 'unknown'}"[:120]
    return None


def health_check(path: Path, text: str, warnings: list[str]) -> tuple[int, list[str]]:
    score = 100
    notes = list(warnings)
    suffix = path.suffix.lower()
    if path.stat().st_size == 0:
        return 0, ["File is empty."]
    if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"} and len(text.strip()) < 25:
        score -= 45
        notes.append("Very little readable text detected.")
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
                if min(w, h) < 700:
                    score -= 20
                    notes.append("Low image resolution may reduce OCR accuracy.")
        except Exception:
            score -= 10
    if warnings:
        score -= min(30, 10 * len(warnings))
    return max(score, 0), list(dict.fromkeys(notes))


def enrich_fields(analysis: FileAnalysis) -> dict[str, Any]:
    text = analysis.extracted_text
    md = analysis.metadata
    fields: dict[str, Any] = {"language": language_detect(text)}
    nip = NIP_RE.search(text)
    iban = IBAN_RE.search(text)
    invoice_no = INVOICE_NO_RE.search(text)
    vat = VAT_RE.search(text)
    net = NET_RE.search(text)
    gross = GROSS_RE.search(text)
    notice = NOTICE_RE.search(text)
    warranty = WARRANTY_RE.search(text)
    fields.update({
        "nip": nip.group(0) if nip else None,
        "iban": re.sub(r"\s", "", iban.group(0)) if iban else None,
        "invoice_number": invoice_no.group(1) if invoice_no else None,
        "vat_rate": vat.group(1) if vat else None,
        "net_amount": _num(net.group(1)) if net else None,
        "gross_amount": _num(gross.group(1)) if gross else md.amount,
        "notice_period": f"{notice.group(1)} {notice.group(2)}" if notice else None,
        "auto_renewal": bool(AUTO_RENEW_RE.search(text)),
    })
    if warranty and md.document_date:
        qty = int(warranty.group(1))
        unit = warranty.group(2).lower()
        months = qty * 12 if unit in {"lat", "years"} else qty
        year = md.document_date.year + (md.document_date.month - 1 + months) // 12
        month = (md.document_date.month - 1 + months) % 12 + 1
        day = min(md.document_date.day, 28)
        fields["warranty_until"] = date(year, month, day).isoformat()
    else:
        fields["warranty_until"] = None
    return fields


def _num(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def expand_query(query: str) -> list[str]:
    words = tokenize(query)
    expanded = set(words)
    for word in words:
        expanded.update(SYNONYMS.get(word, []))
    return sorted(expanded)


def meaning_score(query: str, document: dict[str, Any]) -> float:
    q = Counter(expand_query(query))
    text = " ".join([
        document.get("source_name", ""),
        document.get("extracted_text", ""),
        document.get("case_name") or "",
        " ".join(document.get("tags", [])),
    ])
    d = Counter(tokenize(text))
    if not q or not d:
        return 0.0
    dot = sum(q[k] * d.get(k, 0) for k in q)
    nq = math.sqrt(sum(v*v for v in q.values()))
    nd = math.sqrt(sum(v*v for v in d.values()))
    return dot / (nq * nd) if nq and nd else 0.0


def answer_question(question: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(((meaning_score(question, d), d) for d in documents), key=lambda x: x[0], reverse=True)
    if not ranked or ranked[0][0] <= 0:
        return {"answer": "No matching local document was found.", "sources": []}
    q = question.lower()
    sources = []
    for score, doc in ranked[:5]:
        if score <= 0:
            continue
        md = doc.get("metadata", {})
        if any(k in q for k in ("termin", "deadline", "kiedy", "due")) and md.get("deadline"):
            answer = f"Detected deadline: {md['deadline']}"
        elif any(k in q for k in ("ile", "kwota", "amount", "koszt")) and md.get("amount") is not None:
            answer = f"Detected amount: {md['amount']} {md.get('currency') or ''}".strip()
        else:
            sentences = re.split(r"(?<=[.!?])\s+|\n+", doc.get("extracted_text", ""))
            terms = expand_query(question)
            sentences.sort(key=lambda s: sum(t in s.lower() for t in terms), reverse=True)
            excerpt = next((s.strip() for s in sentences if s.strip()), "")[:450]
            answer = excerpt or f"Relevant document: {doc.get('source_name')}"
        sources.append({"id": doc.get("id"), "name": doc.get("source_name"), "score": round(score, 3)})
        return {"answer": answer, "sources": sources}
    return {"answer": "No direct answer was found in the local index.", "sources": []}
