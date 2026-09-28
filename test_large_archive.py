import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from docpilot.config import get_settings
from docpilot.db import connect, duplicate_groups, list_documents


def _seed_archive(settings, count: int = 1200) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for i in range(count):
        profile = "Company" if i % 2 else "Home"
        case_name = f"Case-{i % 12:02d}"
        metadata = {
            "document_type": "invoice" if i % 3 == 0 else "document",
            "issuer": f"Issuer {i % 25}",
            "deadline": None,
            "confidence": 0.9,
        }
        rows.append(
            (
                f"/archive/document-{i:04d}.txt",
                f"document-{i:04d}.txt",
                f"sha-{i:04d}",
                100 + i,
                "x" * 2000,
                json.dumps(metadata),
                f"Category/{i % 8}",
                f"document-{i:04d}.txt",
                "[]",
                profile,
                case_name,
                None,
                100,
                "[]",
                f"{i:016x}"[-16:],
                now,
                f"{now}-{i:04d}",
            )
        )

    with connect(settings) as conn:
        conn.executemany(
            """
            INSERT INTO documents(
                path,source_name,sha256,size_bytes,extracted_text,metadata_json,category,
                suggested_filename,tags_json,profile,case_name,action_required,health_score,
                health_json,simhash,indexed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )


def test_large_archive_document_page_is_bounded_and_lightweight(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings)
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    response = client.get("/api/documents/page?limit=100&offset=1000")
    assert response.status_code == 200
    page = response.json()

    assert page["total"] == 1200
    assert page["limit"] == 100
    assert page["offset"] == 1000
    assert len(page["items"]) == 100
    assert page["has_more"] is True
    assert all("extracted_text" not in item for item in page["items"])
    assert all("metadata" in item for item in page["items"])


def test_large_archive_document_page_filters_in_sql(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings)
    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    exact = client.get("/api/documents/page", params={"q": "document-1199", "limit": 100})
    assert exact.status_code == 200
    assert exact.json()["total"] == 1
    assert exact.json()["items"][0]["source_name"] == "document-1199.txt"

    company = client.get("/api/documents/page", params={"profile": "Company", "limit": 100})
    assert company.status_code == 200
    assert company.json()["total"] == 600
    assert len(company.json()["items"]) == 100
    assert all(item["profile"] == "Company" for item in company.json()["items"])

    case = client.get("/api/documents/page", params={"case_name": "Case-03", "limit": 250})
    assert case.status_code == 200
    assert case.json()["total"] == 100
    assert all(item["case_name"] == "Case-03" for item in case.json()["items"])


def test_large_archive_schema_indexes_document_ordering(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    with connect(settings) as conn:
        indexes = {row[1] for row in conn.execute("PRAGMA index_list('documents')").fetchall()}
    assert "idx_documents_updated" in indexes


def test_duplicate_groups_can_reuse_already_loaded_documents(tmp_path, monkeypatch):
    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=40)
    docs = list_documents(settings, limit=40)

    import docpilot.db as db_module

    def unexpected_reload(*args, **kwargs):
        raise AssertionError("duplicate_groups reloaded the document list")

    monkeypatch.setattr(db_module, "list_documents", unexpected_reload)
    groups = duplicate_groups(settings, docs)

    assert isinstance(groups, list)
