from pathlib import Path


ROOT = Path(__file__).parent


def test_dynamic_button_collections_use_query_selector_all():
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "$$('.duplicateOpen').forEach" in script
    assert "$$('.duplicateCompare').forEach" in script
    assert "$('.duplicateOpen').forEach" not in script
    assert "$('.duplicateCompare').forEach" not in script
