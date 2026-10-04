from datetime import date
import hashlib
import json
import zipfile

from docpilot.lifepilot import attention_signature, build_case_summary, build_lifepilot_view, build_proof_pack, case_summary_markdown, legacy_attention_signature, lifepilot_queue, next_action_for_document, proof_pack_manifest, proof_pack_preview, verify_proof_pack


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
    assert result["verification"]["source"] == "automatic"
    assert any("Pewność rozpoznania" in item for item in result["decision_basis"])


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


def test_lifepilot_queue_prioritizes_overdue_today_urgent_review_and_soon():
    docs = [
        _doc(id=1, source_name="soon.txt", metadata={"confidence": 0.95, "deadline": "2026-10-14"}),
        _doc(id=2, source_name="overdue.txt", metadata={"confidence": 0.95, "deadline": "2026-10-01"}),
        _doc(id=3, source_name="review.txt", action_required="to-review", metadata={"confidence": 0.4}),
        _doc(id=4, source_name="today.txt", metadata={"confidence": 0.95, "deadline": "2026-10-04"}),
        _doc(id=5, source_name="urgent.txt", metadata={"confidence": 0.95, "deadline": "2026-10-06"}),
        _doc(id=6, source_name="archive.txt", action_required=None, metadata={"confidence": 0.95}),
    ]
    queue = lifepilot_queue(docs, today=date(2026, 10, 4))
    assert [item["id"] for item in queue] == [2, 4, 5, 3, 1]
    assert all(item["id"] != 6 for item in queue)


def test_attention_signature_tracks_semantic_state_not_technical_timestamp():
    original = _doc(updated_at="2026-10-04T10:00:00Z")
    technical_update = _doc(updated_at="2026-10-04T10:01:00Z")
    changed_deadline = _doc(
        updated_at="2026-10-04T10:01:00Z",
        metadata={
            "document_type": "invoice",
            "issuer": "ACME",
            "deadline": "2026-10-07",
            "confidence": 0.95,
            "amount": 199.99,
            "currency": "PLN",
        },
    )
    assert attention_signature(original) == attention_signature(technical_update)
    assert attention_signature(original) != attention_signature(changed_deadline)
    assert legacy_attention_signature(original) != legacy_attention_signature(technical_update)

    verified_once = _doc(metadata={
        "document_type": "invoice",
        "issuer": "ACME",
        "deadline": "2026-10-06",
        "confidence": 0.95,
        "amount": 199.99,
        "currency": "PLN",
        "manual_verified": True,
        "manual_verified_at": "2026-10-04T10:00:00Z",
    })
    verified_again = _doc(metadata={
        "document_type": "invoice",
        "issuer": "ACME",
        "deadline": "2026-10-06",
        "confidence": 0.95,
        "amount": 199.99,
        "currency": "PLN",
        "manual_verified": True,
        "manual_verified_at": "2026-10-04T11:00:00Z",
    })
    assert attention_signature(verified_once) == attention_signature(verified_again)


def test_proof_pack_preview_is_private_and_reports_expected_files(tmp_path):
    source = tmp_path / "evidence.txt"
    source.write_text("hello", encoding="utf-8")
    doc = _doc(path=str(source), source_name=source.name)
    preview = proof_pack_preview(doc, timeline_documents=[doc, _doc(id=8)])
    names = {item["name"] for item in preview["files"]}
    assert "original/evidence.txt" in names
    assert {"manifest.json", "next-action.json", "timeline.json", "SHA256SUMS.txt", "README.txt"} <= names
    assert preview["timeline_items"] == 2
    assert preview["privacy"]["includes_extracted_text"] is False
    assert preview["privacy"]["includes_local_path_in_manifest"] is False
    assert preview["privacy"]["uploads_anything"] is False


def test_manual_verified_low_confidence_uses_verified_action():
    doc = _doc(
        action_required="to-reply",
        metadata={
            "document_type": "official-letter",
            "confidence": 0.4,
            "deadline": "2026-10-08",
            "manual_verified": True,
        },
    )
    result = next_action_for_document(doc, today=date(2026, 10, 4))
    assert result["title"] == "Przygotuj odpowiedź"
    assert result["priority"] == "soon"
    assert "Pewność automatycznego rozpoznania jest niska" not in result["reason"]
    assert result["verification"]["source"] == "manual"
    assert "Dane sprawdzone ręcznie" in result["decision_basis"]


def test_case_summary_is_ordered_private_and_contains_integrity():
    docs = [
        _doc(
            id=2,
            source_name="second.pdf",
            case_name="Sprawa A",
            sha256="hash2",
            metadata={"document_type": "official-letter", "document_date": "2026-10-03", "deadline": "2026-10-10"},
        ),
        _doc(
            id=1,
            source_name="first.pdf",
            case_name="Sprawa A",
            sha256="hash1",
            metadata={"document_type": "invoice", "document_date": "2026-10-01", "deadline": "2026-10-06"},
        ),
        _doc(id=3, source_name="other.pdf", case_name="Inna sprawa"),
    ]
    summary = build_case_summary("Sprawa A", docs)
    assert summary["document_count"] == 2
    assert [item["id"] for item in summary["timeline"]] == [1, 2]
    assert summary["next_deadline"] == "2026-10-06"
    assert summary["timeline"][0]["sha256"] == "hash1"
    assert summary["privacy"]["includes_extracted_text"] is False
    assert summary["privacy"]["includes_local_paths"] is False

    markdown = case_summary_markdown(summary)
    assert "first.pdf" in markdown
    assert "hash1" in markdown
    assert "C:/Docs" not in markdown
    assert "Extracted text" not in markdown


def test_verify_proof_pack_accepts_valid_pack_and_detects_tampering(tmp_path):
    source = tmp_path / "original.txt"
    source.write_text("proof content", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    document = _doc(
        path=str(source),
        source_name=source.name,
        sha256=digest,
        size_bytes=source.stat().st_size,
    )
    pack = tmp_path / "valid-proofpack.zip"
    build_proof_pack(pack, document, timeline_documents=[document])

    verified = verify_proof_pack(pack)
    assert verified["valid"] is True
    assert verified["integrity"]["checksums_verified"] is True
    assert verified["integrity"]["source_matches_manifest"] is True
    assert verified["integrity"]["source_matches_index"] is True
    assert verified["original"] == "original/original.txt"

    tampered = tmp_path / "tampered-proofpack.zip"
    with zipfile.ZipFile(pack, "r") as source_zip, zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        for info in source_zip.infolist():
            data = source_zip.read(info.filename)
            if info.filename == "original/original.txt":
                data = b"changed content"
            target_zip.writestr(info.filename, data)

    failed = verify_proof_pack(tampered)
    assert failed["valid"] is False
    assert any("Checksum mismatch" in error for error in failed["errors"])


def test_verify_proof_pack_rejects_duplicate_or_unsafe_members(tmp_path):
    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("manifest.json", "{}")
    result = verify_proof_pack(duplicate)
    assert result["valid"] is False
    assert any("duplicate filenames" in error.lower() for error in result["errors"])

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape.txt", "x")
        archive.writestr("manifest.json", "{}")
        archive.writestr("next-action.json", "{}")
        archive.writestr("timeline.json", "[]")
        archive.writestr("SHA256SUMS.txt", "")
        archive.writestr("README.txt", "x")
        archive.writestr("original/a.txt", "x")
    result = verify_proof_pack(unsafe)
    assert result["valid"] is False
    assert any("unsafe member paths" in error.lower() for error in result["errors"])
