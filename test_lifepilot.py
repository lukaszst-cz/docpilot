from datetime import date
import hashlib
import json
import zipfile

from docpilot.lifepilot import build_lifepilot_view, build_proof_pack, next_action_for_document, proof_pack_manifest


def _doc(**overrides):
    base = {
        "id": 7,
        "source_name": "faktura.pdf",
        "path": "C:/Docs/faktura.pdf",
        "sha256": "abc123",
        "size_bytes": 1234,
        "category": "Finance/Invoices",
        "profile": "Home",
        "case_name": "ACME",
        "action_required": "to-pay",
        "metadata": {
            "document_type": "invoice",
            "issuer": "ACME",
            "deadline": "2026-10-06",
            "confidence": 0.95,
            "amount": 199.99,
            "currency": "PLN",
        },
    }
    base.update(overrides)
    return base


def test_next_action_uses_existing_action_and_deadline():
    result = next_action_for_document(_doc(), today=date(2026, 10, 4))
    assert result["title"] == "Zweryfikuj i opłać dokument"
    assert result["priority"] == "urgent"
    assert result["days_remaining"] == 2
    assert result["due_date"] == "2026-10-06"
    assert result["available_actions"]["proof_pack"] is True
    assert result["available_actions"]["calendar"] is True


def test_low_confidence_requires_review_before_action():
    doc = _doc(metadata={"document_type": "invoice", "confidence": 0.4, "deadline": "2026-10-20"})
    result = next_action_for_document(doc, today=date(2026, 10, 4))
    assert result["priority"] == "review"
    assert "sprawdź" in result["title"].lower()


def test_proof_pack_manifest_does_not_expose_local_path():
    manifest = proof_pack_manifest(_doc())
    assert manifest["format"] == "lifepilot-proof-pack"
    assert manifest["integrity"]["algorithm"] == "sha256"
    assert manifest["integrity"]["digest"] == "abc123"
    assert "path" not in manifest["document"]
    assert manifest["privacy"]["includes_extracted_text"] is False
    assert manifest["privacy"]["includes_local_path"] is False


def test_combined_view_exposes_next_action_and_proof_pack():
    view = build_lifepilot_view(_doc(), today=date(2026, 10, 4))
    assert set(view) == {"next_action", "proof_pack"}


def test_build_proof_pack_contains_original_manifest_timeline_and_checksums(tmp_path):
    source = tmp_path / "letter.txt"
    source.write_text("Termin odpowiedzi: 6.10.2026", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    document = _doc(path=str(source), source_name=source.name, sha256=digest, size_bytes=source.stat().st_size)
    destination = tmp_path / "proofpack.zip"

    build_proof_pack(destination, document, timeline_documents=[document])

    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        assert "original/letter.txt" in names
        assert {"manifest.json", "next-action.json", "timeline.json", "SHA256SUMS.txt", "README.txt"} <= names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["integrity"]["computed_digest"] == digest
        assert manifest["integrity"]["matches_index"] is True
        assert "C:/Docs" not in archive.read("manifest.json").decode("utf-8")
        sums = archive.read("SHA256SUMS.txt").decode("utf-8")
        assert digest in sums
