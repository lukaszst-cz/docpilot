from docpilot.app import STATIC_DIR, TEMPLATE_DIR, _local_origin_allowed


def test_local_origins_are_allowed():
    assert _local_origin_allowed("http://127.0.0.1:8765")
    assert _local_origin_allowed("http://localhost:9999")
    assert _local_origin_allowed("http://[::1]:8765")


def test_remote_and_invalid_origins_are_blocked():
    assert not _local_origin_allowed("https://example.com")
    assert not _local_origin_allowed("https://docpilot.example")
    assert not _local_origin_allowed("not-an-origin")


def test_source_ui_assets_are_resolved():
    assert (TEMPLATE_DIR / "index.html").exists()
    assert (STATIC_DIR / "app.css").exists()
    assert (STATIC_DIR / "app.js").exists()
