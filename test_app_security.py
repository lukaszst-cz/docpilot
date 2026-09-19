
from pathlib import Path

from fastapi.testclient import TestClient

from docpilot.app import LOG_PATH, STATIC_DIR, TEMPLATE_DIR, _local_origin_allowed, app, settings


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


def test_source_static_route_does_not_expose_python_files():
    client = TestClient(app)
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.py").status_code == 404


def test_diagnostics_are_local_and_log_is_stable():
    client = TestClient(app)
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert data["version"]
    assert data["database"] in {"ok", "missing"}
    assert Path(data["data_root"]).resolve() == settings.root.resolve()
    assert LOG_PATH.parent.resolve() == settings.state.resolve()
    assert "data_root" not in data["safe_report"]
    assert "log_path" not in data["safe_report"]
