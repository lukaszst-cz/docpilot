from datetime import date

from docpilot.lifepilot import build_lifepilot_view, next_action_for_document, proof_pack_manifest


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


def test_low_confidence_requires_review_before_action():
    doc = _doc(metadata={"document_type": "invoice", "confidence": 0.4, "deadline": "2026-10-20"})
    result = next_action_for_document(doc, today=date(2026, 10, 4))
    assert result["priority"] == "review"
    assert "sprawdź" in result["title"].lower()


def test_proof_pack_is_minimal_and_contains_integrity_data():
    manifest = proof_pack_manifest(_doc())
    assert manifest["format"] == "lifepilot-proof-pack"
    assert manifest["integrity"]["algorithm"] == "sha256"
    assert manifest["integrity"]["digest"] == "abc123"
    assert manifest["privacy"]["includes_extracted_text"] is False
    assert manifest["privacy"]["includes_file_bytes"] is False


def test_combined_view_exposes_next_action_and_proof_pack():
    view = build_lifepilot_view(_doc(), today=date(2026, 10, 4))
    assert set(view) == {"next_action", "proof_pack"}
