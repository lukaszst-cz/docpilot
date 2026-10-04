from pathlib import Path


ROOT = Path(__file__).parent


def test_windows_package_includes_lifepilot_product_page():
    spec = (ROOT / "packaging" / "docpilot.spec").read_text(encoding="utf-8")
    assert 'ROOT / "lifepilot.html"' in spec
    assert '"docpilot/templates"' in spec


def test_lifepilot_product_page_states_preview_and_limits():
    page = (ROOT / "lifepilot.html").read_text(encoding="utf-8")
    assert "LIFE PILOT PREVIEW" in page
    assert "ProofPack to nie kwalifikowany podpis" in page
    assert "DocPilot v4.0.0" in page
    assert "Co teraz?" in page
    assert "LifePilot Preview 4.9" in page
    assert "CasePack" in page
    assert "Case Readiness" in page
    assert "Decision Trail" in page
    assert "Release self-test" in page
    assert "kontrolowany pilot" in page
