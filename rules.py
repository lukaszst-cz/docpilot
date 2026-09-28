from __future__ import annotations

from typing import Any


def rule_matches(document: dict[str, Any], rule: dict[str, Any]) -> bool:
    if not rule.get("enabled", True):
        return False

    cond = rule.get("condition") or {}
    text = (document.get("extracted_text") or "").lower()
    md = document.get("metadata") or {}

    if cond.get("issuer_contains") and cond["issuer_contains"].lower() not in (md.get("issuer") or "").lower():
        return False
    if cond.get("text_contains") and cond["text_contains"].lower() not in text:
        return False
    if cond.get("document_type") and cond["document_type"] != md.get("document_type"):
        return False
    return True


def apply_rules(document: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    category = document.get("category")
    profile = document.get("profile") or "Home"
    tags = set(document.get("tags", []))
    matched_rules: list[dict[str, Any]] = []

    # Rules are supplied oldest -> newest. Later matching rules intentionally
    # override category/profile selected by earlier rules while tags accumulate.
    for rule in rules:
        if not rule_matches(document, rule):
            continue
        category = rule.get("target_category") or category
        profile = rule.get("target_profile") or profile
        tags.update(rule.get("target_tags") or [])
        matched_rules.append({
            "id": rule.get("id"),
            "name": rule.get("name") or "Rule",
        })

    return {
        "category": category,
        "profile": profile,
        "tags": sorted(tags),
        "matched_rules": matched_rules,
    }
