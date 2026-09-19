from pathlib import Path
from docpilot.diffing import compare_documents


def test_diff(tmp_path: Path):
    a = tmp_path / "a.txt"; b = tmp_path / "b.txt"
    a.write_text("Payment 14 days\nPenalty 0.2%", encoding="utf-8")
    b.write_text("Payment 30 days\nPenalty 0.5%", encoding="utf-8")
    result = compare_documents(a, b)
    assert result["added_lines"] >= 1
    assert result["removed_lines"] >= 1
