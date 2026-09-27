import importlib

from fastapi.testclient import TestClient


def test_duplicate_compare_requires_two_different_ids():
    app_module = importlib.import_module("docpilot.app")
    client = TestClient(app_module.app)

    response = client.post("/api/duplicates/compare", json={"left_id": 3, "right_id": 3})
    assert response.status_code == 400


def test_duplicate_compare_returns_named_pair(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("invoice total 100", encoding="utf-8")
    right.write_text("invoice total 101", encoding="utf-8")

    docs = {
        1: {"id": 1, "source_name": "left.txt", "path": str(left)},
        2: {"id": 2, "source_name": "right.txt", "path": str(right)},
    }
    monkeypatch.setattr(app_module, "get_document", lambda _settings, doc_id: docs.get(doc_id))

    client = TestClient(app_module.app)
    response = client.post("/api/duplicates/compare", json={"left_id": 1, "right_id": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["left"]["name"] == "left.txt"
    assert data["right"]["name"] == "right.txt"
    assert data["similarity"] < 1


def test_exact_duplicate_uses_hash_without_text_diff(monkeypatch, tmp_path):
    app_module = importlib.import_module("docpilot.app")
    left = tmp_path / "a.pdf"
    right = tmp_path / "b.pdf"
    left.write_bytes(b"same")
    right.write_bytes(b"same")
    docs = {
        1: {"id": 1, "source_name": "a.pdf", "path": str(left), "sha256": "same-hash"},
        2: {"id": 2, "source_name": "b.pdf", "path": str(right), "sha256": "same-hash"},
    }
    monkeypatch.setattr(app_module, "get_document", lambda _settings, doc_id: docs.get(doc_id))

    def fail_compare(*_args, **_kwargs):
        raise AssertionError("exact duplicates should not be text-diffed")

    monkeypatch.setattr(app_module, "compare_documents", fail_compare)
    client = TestClient(app_module.app)
    response = client.post("/api/duplicates/compare", json={"left_id": 1, "right_id": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["exact_hash_match"] is True
    assert data["similarity"] == 1.0
