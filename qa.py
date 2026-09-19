from __future__ import annotations

import re
from datetime import date
from typing import Any

from .semantic import semantic_rank


def answer_local(question: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    q = question.strip().lower()
    if not q:
        return {"answer": "Question is empty.", "sources": [], "mode": "none"}

    ranked = semantic_rank(question, documents, limit=20)
    matched = [r.document for r in ranked if r.score >= 0.015]
    if not matched:
        return {"answer": "No matching local document was found.", "sources": [], "mode": "search"}

    # Structured action queries.
    if _has(q, "wymagają odpowiedzi", "wymagaja odpowiedzi", "do odpowiedzi", "need reply", "require response"):
        items = [d for d in matched if d.get("action_required") == "to-reply"]
        return _list_answer("Documents marked as requiring a reply", items, ranked, mode="structured-actions")

    if _has(q, "do zapłaty", "do zaplaty", "wymagają zapłaty", "wymagaja zaplaty", "to pay", "need payment"):
        items = [d for d in matched if d.get("action_required") == "to-pay"]
        return _list_answer("Documents marked for payment", items, ranked, mode="structured-actions")

    # Sum detected monetary fields in the matching set. We describe exactly what
    # is being summed rather than inferring legal/accounting meaning such as
    # "received" or "owed" without evidence.
    if _has(q, "ile łącznie", "ile lacznie", "suma", "łącznie", "lacznie", "total", "sum"):
        amounts = []
        for d in matched:
            md = d.get("metadata") or {}
            value = md.get("amount")
            if value is None:
                value = md.get("gross_amount")
            if value is not None:
                amounts.append((float(value), md.get("currency") or "", d))
        if amounts:
            by_currency: dict[str, float] = {}
            for value, currency, _ in amounts:
                by_currency[currency] = by_currency.get(currency, 0.0) + value
            total_text = ", ".join(f"{v:.2f} {k}".strip() for k, v in by_currency.items())
            return {
                "answer": f"Sum of detected amounts across {len(amounts)} matching documents: {total_text}. Review the source documents before treating this as an accounting total.",
                "sources": _sources(ranked, ids={int(x[2]["id"]) for x in amounts}),
                "mode": "structured-sum",
            }

    if _has(q, "najbliższy termin", "najblizszy termin", "next deadline", "co jest najpilniejsze", "najpilniejsze"):
        dated = []
        for d in matched:
            md = d.get("metadata") or {}
            raw = md.get("deadline") or md.get("warranty_until")
            if raw:
                try:
                    dated.append((date.fromisoformat(str(raw)), d))
                except ValueError:
                    pass
        if dated:
            dated.sort(key=lambda x: x[0])
            day, doc = dated[0]
            return {"answer": f"Nearest detected date: {day.isoformat()} — {doc.get('source_name')}.", "sources": _sources(ranked, ids={int(doc['id'])}), "mode": "structured-deadline"}

    if _has(q, "kiedy", "termin", "deadline", "ważne do", "wazne do", "expires", "wygasa", "kończy się", "konczy sie"):
        for d in matched:
            md = d.get("metadata") or {}
            raw = md.get("deadline") or md.get("warranty_until")
            if raw:
                label = "warranty date" if md.get("warranty_until") == raw and not md.get("deadline") else "deadline"
                return {"answer": f"Detected {label}: {raw} in {d.get('source_name')}.", "sources": _sources(ranked, ids={int(d['id'])}), "mode": "structured-date"}

    if _has(q, "ile", "kwota", "amount", "koszt", "wartość", "wartosc"):
        for d in matched:
            md = d.get("metadata") or {}
            if md.get("amount") is not None:
                return {"answer": f"Detected amount: {md['amount']} {md.get('currency') or ''} in {d.get('source_name')}.".strip(), "sources": _sources(ranked, ids={int(d['id'])}), "mode": "structured-amount"}

    # Extractive local answer from the best semantically ranked sentences.
    terms = _terms(question)
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for rank in ranked[:8]:
        doc = rank.document
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(doc.get("extracted_text") or "")):
            sentence = sentence.strip()
            if len(sentence) < 8:
                continue
            score = rank.score + 0.035 * sum(t in sentence.lower() for t in terms)
            candidates.append((score, sentence[:700], doc))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates:
        score, sentence, doc = candidates[0]
        return {"answer": sentence, "sources": _sources(ranked, ids={int(doc['id'])}), "mode": "extractive"}
    return {"answer": f"Most relevant local document: {matched[0].get('source_name')}", "sources": _sources(ranked), "mode": "search"}


def _list_answer(title: str, items: list[dict[str, Any]], ranked, mode: str) -> dict[str, Any]:
    if not items:
        return {"answer": f"{title}: none found in the matching local documents.", "sources": _sources(ranked), "mode": mode}
    names = "; ".join(str(d.get("source_name")) for d in items[:10])
    return {"answer": f"{title} ({len(items)}): {names}", "sources": _sources(ranked, ids={int(d['id']) for d in items}), "mode": mode}


def _sources(ranked, ids: set[int] | None = None) -> list[dict[str, Any]]:
    out = []
    for r in ranked[:10]:
        d = r.document
        if ids is not None and int(d.get("id") or 0) not in ids:
            continue
        out.append({"id": d.get("id"), "name": d.get("source_name"), "score": round(r.score, 3), "path": d.get("path")})
    return out[:6]


def _terms(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[\wąćęłńóśźż-]{3,}", text, re.I)]


def _has(text: str, *phrases: str) -> bool:
    return any(p in text for p in phrases)
