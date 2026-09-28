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


def test_large_archive_dashboard_does_not_load_full_document_rows(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1200)
    monkeypatch.setattr(app_module, "settings", settings)

    def unexpected_full_load(*args, **kwargs):
        raise AssertionError("dashboard loaded full document rows")

    monkeypatch.setattr(app_module, "list_documents", unexpected_full_load)
    client = TestClient(app_module.app)

    response = client.get("/api/dashboard")
    assert response.status_code == 200
    dashboard = response.json()

    assert dashboard["documents"] == 1200
    assert dashboard["actions"] == 0
    assert dashboard["unhealthy"] == 0
    assert dashboard["cases"] == 12
    assert dashboard["profiles"] == ["Company", "Home"]
    assert dashboard["deadline_count"] == 0
    assert dashboard["deadlines"] == []


def test_duplicate_group_count_uses_sql_for_exact_groups(tmp_path):
    from docpilot.db import duplicate_group_count

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=30)

    with connect(settings) as conn:
        conn.execute("UPDATE documents SET simhash=NULL")
        conn.execute("UPDATE documents SET sha256='same-a' WHERE id IN (1,2)")
        conn.execute("UPDATE documents SET sha256='same-b' WHERE id IN (3,4,5)")

    assert duplicate_group_count(settings) == 2


def test_large_archive_semantic_candidates_are_bounded_and_relevant(monkeypatch, tmp_path):
    import docpilot.app as app_module
    from docpilot.db import semantic_candidate_documents

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1200)

    with connect(settings) as conn:
        conn.execute(
            """
            UPDATE documents
            SET extracted_text='special insurance flooding claim',
                metadata_json=?,
                updated_at='2020-01-01T00:00:00+00:00'
            WHERE source_name='document-0001.txt'
            """,
            (json.dumps({
                "document_type": "insurance",
                "issuer": "Special Insurer",
                "deadline": None,
                "confidence": 0.9,
            }),),
        )

    candidates = semantic_candidate_documents(settings, "zalanie ubezpieczenie", limit=750)
    assert len(candidates) <= 750
    assert any(item["source_name"] == "document-0001.txt" for item in candidates)

    monkeypatch.setattr(app_module, "settings", settings)
    client = TestClient(app_module.app)

    search = client.get("/api/search", params={"q": "zalanie ubezpieczenie", "limit": 20})
    assert search.status_code == 200
    assert any(item["source_name"] == "document-0001.txt" for item in search.json())

    qa = client.post("/api/qa", json={"question": "zalanie ubezpieczenie"})
    assert qa.status_code == 200
    assert any(source["name"] == "document-0001.txt" for source in qa.json()["sources"])


def test_large_archive_common_search_is_capped_before_semantic_ranking(tmp_path):
    from docpilot.db import semantic_candidate_documents

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1200)

    candidates = semantic_candidate_documents(settings, "document", limit=750)

    assert len(candidates) == 750


def test_large_archive_review_queue_only_loads_candidates(monkeypatch, tmp_path):
    import docpilot.app as app_module

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1200)

    with connect(settings) as conn:
        conn.execute("UPDATE documents SET simhash=NULL")
        conn.execute(
            "UPDATE documents SET metadata_json=? WHERE id=1",
            (json.dumps({
                "document_type": "document",
                "issuer": "Issuer 1",
                "deadline": None,
                "confidence": 0.4,
            }),),
        )
        conn.execute("UPDATE documents SET health_score=40 WHERE id=2")
        conn.execute("UPDATE documents SET action_required='to-review' WHERE id=3")
        conn.execute("UPDATE documents SET extracted_text='' WHERE id=4")
        conn.execute(
            "UPDATE documents SET extracted_text='Please reply by the date shown in this letter' WHERE id=5"
        )
        conn.execute("UPDATE documents SET sha256='exact-review-pair' WHERE id IN (10,11)")

    monkeypatch.setattr(app_module, "settings", settings)

    def unexpected_full_load(*args, **kwargs):
        raise AssertionError("Review Queue loaded the full document list")

    monkeypatch.setattr(app_module, "list_documents", unexpected_full_load)
    client = TestClient(app_module.app)

    response = client.get("/api/review")
    assert response.status_code == 200
    queue = response.json()
    by_id = {int(item["id"]): item for item in queue}

    assert {1, 2, 3, 4, 5, 10, 11}.issubset(by_id)
    assert "low-confidence" in {reason["code"] for reason in by_id[1]["reasons"]}
    assert "scan-health" in {reason["code"] for reason in by_id[2]["reasons"]}
    assert "action-review" in {reason["code"] for reason in by_id[3]["reasons"]}
    assert "no-text" in {reason["code"] for reason in by_id[4]["reasons"]}
    assert "uncertain-deadline" in {reason["code"] for reason in by_id[5]["reasons"]}
    assert "duplicate" in {reason["code"] for reason in by_id[10]["reasons"]}
    assert "duplicate" in {reason["code"] for reason in by_id[11]["reasons"]}


def test_review_candidate_documents_are_bounded(tmp_path):
    from docpilot.db import review_candidate_documents

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1800)

    with connect(settings) as conn:
        conn.execute("UPDATE documents SET health_score=50, simhash=NULL")

    documents, groups = review_candidate_documents(settings, limit=1500)

    assert len(documents) == 1000
    assert groups == []


def test_duplicate_api_uses_lightweight_rows_without_full_document_load(monkeypatch, tmp_path):
    import docpilot.app as app_module
    import docpilot.db as db_module

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1600)
    with connect(settings) as conn:
        conn.execute("UPDATE documents SET simhash=NULL")
        conn.execute("UPDATE documents SET sha256='exact-large-pair' WHERE id IN (20,21)")

    monkeypatch.setattr(app_module, "settings", settings)

    def unexpected_full_load(*args, **kwargs):
        raise AssertionError("Duplicate Finder loaded full document rows")

    monkeypatch.setattr(db_module, "list_documents", unexpected_full_load)
    client = TestClient(app_module.app)

    response = client.get("/api/duplicates")
    assert response.status_code == 200
    groups = response.json()
    exact = next(group for group in groups if group["kind"] == "exact")

    assert {int(item["id"]) for item in exact["documents"]} == {20, 21}
    assert all("extracted_text" not in item for item in exact["documents"])
    assert all("metadata" not in item for item in exact["documents"])
    assert all({"id", "path", "source_name", "sha256", "simhash", "updated_at"}.issubset(item) for item in exact["documents"])


def test_duplicate_display_groups_chunks_large_exact_groups(tmp_path):
    from docpilot.db import duplicate_display_groups

    settings = get_settings(tmp_path / "DocPilotData")
    _seed_archive(settings, count=1200)
    with connect(settings) as conn:
        conn.execute("UPDATE documents SET simhash=NULL, sha256='one-large-exact-group'")

    groups = duplicate_display_groups(settings)
    assert len(groups) == 1
    assert groups[0]["kind"] == "exact"
    assert len(groups[0]["documents"]) == 1200
    assert all("extracted_text" not in item for item in groups[0]["documents"])
