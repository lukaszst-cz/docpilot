from pathlib import Path

from docpilot.analyze import analyze_file
from docpilot.config import get_settings
from docpilot.db import duplicate_groups, list_documents, upsert_document


def test_index_and_exact_duplicate(tmp_path: Path):
    settings = get_settings(tmp_path / "state")
    p1 = tmp_path / "a.txt"
    p2 = tmp_path / "b.txt"
    p1.write_text("same invoice 12.34 PLN", encoding="utf-8")
    p2.write_text("same invoice 12.34 PLN", encoding="utf-8")
    for p in (p1, p2):
        a = analyze_file(p)
        upsert_document(settings, a, tags=a.tags, simhash=a.simhash)
    assert len(list_documents(settings)) == 2
    groups = duplicate_groups(settings)
    assert any(g["kind"] == "exact" and len(g["documents"]) == 2 for g in groups)
