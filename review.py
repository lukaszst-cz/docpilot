from __future__ import annotations

from typing import Any

from .intelligence import tokenize

DEADLINE_HINTS = ("termin", "deadline", "do dnia", "due date", "ważne do", "odpowiedź do", "reply by")


def build_review_queue(documents: list[dict[str, Any]], duplicate_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    duplicate_ids: set[int] = set()
    duplicate_kind: dict[int, str] = {}
    for group in duplicate_groups:
        for d in group.get("documents", []):
            try:
                ident = int(d["id"])
                duplicate_ids.add(ident)
                duplicate_kind[ident] = group.get("kind", "duplicate")
            except Exception:
                pass

    queue: list[dict[str, Any]] = []
    for d in documents:
        reasons: list[dict[str, Any]] = []
        md = d.get("metadata") or {}
        confidence = float(md.get("confidence") or 0)
        health = int(d.get("health_score") or 100)
        text = str(d.get("extracted_text") or "")
        low = text.lower()
        doc_id = int(d.get("id") or 0)

        if confidence < 0.65:
            reasons.append({"code": "low-confidence", "severity": "high" if confidence < 0.45 else "medium", "detail": f"Metadata confidence {confidence:.0%}"})
        if health < 70:
            reasons.append({"code": "scan-health", "severity": "high" if health < 45 else "medium", "detail": f"Document health {health}/100"})
        if any(h in low for h in DEADLINE_HINTS) and not md.get("deadline"):
            reasons.append({"code": "uncertain-deadline", "severity": "medium", "detail": "Deadline language detected but no date was confidently extracted."})
        if doc_id in duplicate_ids:
            reasons.append({"code": "duplicate", "severity": "medium", "detail": f"Possible {duplicate_kind.get(doc_id)} duplicate."})
        if d.get("action_required") == "to-review":
            reasons.append({"code": "action-review", "severity": "medium", "detail": "Document requires manual review."})
        if not text.strip():
            reasons.append({"code": "no-text", "severity": "high", "detail": "No searchable text was extracted."})

        if reasons:
            severity_order = {"high": 0, "medium": 1, "low": 2}
            severity = sorted((r["severity"] for r in reasons), key=lambda s: severity_order[s])[0]
            queue.append({
                "id": doc_id,
                "name": d.get("source_name"),
                "path": d.get("path"),
                "severity": severity,
                "reasons": reasons,
                "category": d.get("category"),
                "case_name": d.get("case_name"),
                "metadata": md,
            })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    queue.sort(key=lambda x: (severity_order.get(x["severity"], 9), x.get("name") or ""))
    return queue
