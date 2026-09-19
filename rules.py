from __future__ import annotations

from typing import Any


def apply_rules(document: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    category = document.get("category")
    profile = document.get("profile") or "Home"
    tags = set(document.get("tags", []))
    text = (document.get("extracted_text") or "").lower()
    md = document.get("metadata") or {}
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        cond = rule.get("condition") or {}
        ok = True
        if cond.get("issuer_contains"):
            ok &= cond["issuer_contains"].lower() in (md.get("issuer") or "").lower()
        if cond.get("text_contains"):
            ok &= cond["text_contains"].lower() in text
        if cond.get("document_type"):
            ok &= cond["document_type"] == md.get("document_type")
        if not ok:
            continue
        category = rule.get("target_category") or category
        profile = rule.get("target_profile") or profile
        tags.update(rule.get("target_tags") or [])
    return {"category": category, "profile": profile, "tags": sorted(tags)}
