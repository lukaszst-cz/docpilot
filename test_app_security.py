
from pathlib import Path

from fastapi.testclient import TestClient

from docpilot.app import LOG_PATH, STATIC_DIR, TEMPLATE_DIR, _diagnostic_assessment, _local_origin_allowed, app, settings


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


def test_diagnostic_assessment_flags_database_schema_and_disk_problems():
    healthy = _diagnostic_assessment({
        "database": "ok",
        "database_integrity": "ok",
        "schema_version": 4,
        "supported_schema_version": 4,
        "free_space_gb": 10.0,
    })
    assert healthy["status"] == "ok"
    assert healthy["recommendations"] == ["No immediate maintenance action is required."]

    warning = _diagnostic_assessment({
        "database": "ok",
        "database_integrity": "ok",
        "schema_version": 4,
        "supported_schema_version": 4,
        "free_space_gb": 0.75,
    })
    assert warning["status"] == "warning"
    assert any(item["code"] == "disk" and item["status"] == "warning" for item in warning["checks"])

    broken = _diagnostic_assessment({
        "database": "ok",
        "database_integrity": "corrupt",
        "schema_version": 5,
        "supported_schema_version": 4,
        "free_space_gb": 0.1,
    })
    assert broken["status"] == "error"
    assert any(item["code"] == "database" and item["status"] == "error" for item in broken["checks"])
    assert any(item["code"] == "schema" and item["status"] == "error" for item in broken["checks"])
    assert any(item["code"] == "disk" and item["status"] == "error" for item in broken["checks"])


def test_downloadable_diagnostic_report_excludes_private_paths_and_document_content():
    client = TestClient(app)
    response = client.get("/api/diagnostics/report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "attachment; filename=\"docpilot-safe-diagnostics.txt\"" in response.headers["content-disposition"]

    text = response.text
    assert "DocPilot safe diagnostic report" in text
    assert "Overall status:" in text
    assert "Recommended next steps:" in text
    assert str(settings.root) not in text
    assert str(LOG_PATH) not in text
    assert "extracted_text" not in text
