from pathlib import Path


ROOT = Path(__file__).parent


def test_desktop_window_marks_embedded_client_mode():
    source = (ROOT / "desktop.py").read_text(encoding="utf-8")

    assert 'http://127.0.0.1:8765/?client=desktop' in source
    assert 'webview.create_window("DocPilot"' in source
