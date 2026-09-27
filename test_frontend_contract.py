from pathlib import Path
import re


ROOT = Path(__file__).parent


def test_dynamic_button_collections_use_query_selector_all():
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "$('.duplicateOpen').forEach" in script
    assert "$('.duplicateCompare').forEach" in script
    assert re.search(r"(?<!\$)\$\('\.duplicateOpen'\)\.forEach", script) is None
    assert re.search(r"(?<!\$)\$\('\.duplicateCompare'\)\.forEach", script) is None


def test_core_navigation_exposes_accessibility_hooks():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'class="skipLink"' in html
    assert 'id="mainContent" tabindex="-1"' in html
    assert 'id="viewTitle" tabindex="-1"' in html
    assert 'aria-current="page"' in html
    assert 'aria-label="Search local documents"' in html
    assert 'aria-label="Ask a question about local documents"' in html
    assert "b.setAttribute('aria-current','page')" in script
    assert "$('#nav')?.addEventListener('keydown'" in script
