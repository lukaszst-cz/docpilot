from __future__ import annotations

import difflib
from pathlib import Path

from .extract import extract_text


def compare_documents(a: Path, b: Path) -> dict:
    ta, wa = extract_text(a)
    tb, wb = extract_text(b)
    a_lines = [x.rstrip() for x in ta.splitlines()]
    b_lines = [x.rstrip() for x in tb.splitlines()]
    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile=a.name, tofile=b.name, lineterm=""))
    matcher = difflib.SequenceMatcher(None, ta, tb)
    added = sum(1 for x in diff if x.startswith("+") and not x.startswith("+++"))
    removed = sum(1 for x in diff if x.startswith("-") and not x.startswith("---"))
    return {
        "similarity": round(matcher.ratio(), 4),
        "added_lines": added,
        "removed_lines": removed,
        "diff": "\n".join(diff[:2500]),
        "warnings": wa + wb,
    }
