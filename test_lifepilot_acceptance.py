from copy import deepcopy
from datetime import date

from PIL import Image

from docpilot.analyze import analyze_file
from docpilot.lifepilot import (
    build_case_pack,
    case_pack_preview,
    case_readiness,
    decision_field_changes,
    decision_summary,
    next_action_for_document,
    verify_case_pack,
)


def _write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return analyze_file(path)


def _life(analysis):
    return next_action_for_document(analysis.model_dump(mode="json"), today=date(2026, 10, 4))


def test_acceptance_invoice_to_pay(tmp_path):
    analysis = _write(
        tmp_path,
        "invoice.txt",
        "ACME Sp. z o.o.\nFaktura VAT nr FV/10/2026\nData: 01.10.2026\nTermin platnosci: 06.10.2026\nDo zaplaty 199,99 PLN",
    )
    assert analysis.metadata.document_type == "invoice"
    assert analysis.metadata.deadline.isoformat() == "2026-10-06"
    assert analysis.action_required == "to-pay"
    assert _life(analysis)["priority"] == "urgent"


def test_acceptance_official_letter_to_reply(tmp_path):
    analysis = _write(
        tmp_path,
        "official.txt",
        "Urzad Testowy\nWezwanie do zlozenia wyjasnien\nData: 01.10.2026\nOdpowiedz do 10.10.2026",
    )
    assert analysis.metadata.document_type == "official-letter"
    assert analysis.action_required == "to-reply"
    assert _life(analysis)["title"] == "Przygotuj odpowiedź"


def test_acceptance_insurance_policy_has_deadline(tmp_path):
    analysis = _write(
        tmp_path,
        "policy.txt",
        "PZU SA\nPolisa ubezpieczenia nr POL/2026/001\nData: 01.10.2026\nWazne do 31.12.2026",
    )
    assert analysis.metadata.document_type == "insurance"
    assert analysis.metadata.deadline.isoformat() == "2026-12-31"
    assert _life(analysis)["due_date"] == "2026-12-31"


def test_acceptance_warranty_builds_expiry(tmp_path):
    analysis = _write(
        tmp_path,
        "warranty.txt",
        "Sklep Testowy\nGwarancja 24 months\nData: 01.10.2026\nProdukt testowy",
    )
    assert analysis.metadata.document_type == "warranty"
    assert str(analysis.metadata.warranty_until) == "2028-10-01"
    assert _life(analysis)["due_date"] == "2028-10-01"


def test_acceptance_contract_requires_signature(tmp_path):
    analysis = _write(
        tmp_path,
        "contract.txt",
        "Firma Testowa\nUmowa o swiadczenie uslug\nData: 01.10.2026\nProsze o podpis dokumentu.",
    )
    assert analysis.metadata.document_type == "contract"
    assert analysis.action_required == "to-sign"
    assert _life(analysis)["title"] == "Sprawdź i podpisz dokument"


def test_acceptance_school_document_classification(tmp_path):
    analysis = _write(
        tmp_path,
        "school.txt",
        "Szkoła Podstawowa Testowa\nInformacja Librus dla ucznia i rodzica\nData: 01.10.2026\nZebranie organizacyjne.",
    )
    assert analysis.metadata.document_type == "school"
    assert analysis.suggested_category == "School"


def test_acceptance_insurance_claim_creates_case_hint(tmp_path):
    analysis = _write(
        tmp_path,
        "claim.txt",
        "UNIQA\nSzkoda ubezpieczeniowa nr SZK/2026/77\nPolisa POL/2026/11\nData: 01.10.2026",
    )
    assert analysis.metadata.document_type == "insurance"
    assert analysis.suggested_case
    assert "Insurance case" in analysis.suggested_case or "UNIQA" in analysis.suggested_case


def test_acceptance_poor_scan_fails_toward_manual_review(tmp_path):
    path = tmp_path / "poor-scan.png"
    Image.new("RGB", (240, 180), "white").save(path)
    analysis = analyze_file(path)
    result = _life(analysis)
    assert analysis.health_score < 70
    assert analysis.metadata.confidence < 0.65
    assert result["priority"] == "review"
    assert "sprawdź" in result["title"].lower()


def test_acceptance_document_without_deadline_archives(tmp_path):
    analysis = _write(
        tmp_path,
        "note.txt",
        "Notatka testowa\nMaterial archiwalny bez terminu i bez wymaganej odpowiedzi.",
    )
    assert analysis.metadata.deadline is None
    assert analysis.action_required == "to-archive"


def test_acceptance_ambiguous_deadline_fails_toward_review(tmp_path):
    analysis = _write(
        tmp_path,
        "ambiguous.txt",
        "Pismo informacyjne\nData: 01.10.2026\nTermin: 06.10.2026\nBrak informacji czego dotyczy termin.",
    )
    assert analysis.metadata.deadline is None
    result = _life(analysis)
    assert analysis.metadata.confidence < 0.65
    assert result["priority"] == "review"


def _indexed_document(analysis, doc_id: int, case_name: str):
    payload = analysis.model_dump(mode="json")
    return {
        "id": doc_id,
        "path": payload["source_path"],
        "source_name": payload["source_name"],
        "sha256": payload["sha256"],
        "size_bytes": payload["size_bytes"],
        "metadata": payload["metadata"],
        "case_name": case_name,
        "action_required": payload["action_required"],
        "category": payload["suggested_category"],
        "profile": "Home",
        "updated_at": "2026-10-04T12:00:00+00:00",
    }


def test_acceptance_multiple_dates_use_explicit_deadline_phrase(tmp_path):
    analysis = _write(
        tmp_path,
        "multi-date-invoice.txt",
        "ACME Sp. z o.o.\nFaktura VAT nr FV/20/2026\n"
        "Data wystawienia: 01.10.2026\nData sprzedazy: 30.09.2026\n"
        "Termin platnosci: 14.10.2026\nDo zaplaty 450,00 PLN",
    )
    assert analysis.metadata.document_date.isoformat() == "2026-10-01"
    assert analysis.metadata.deadline.isoformat() == "2026-10-14"
    result = _life(analysis)
    assert result["due_date"] == "2026-10-14"
    assert result["action_code"] == "to-pay"


def test_acceptance_two_document_case_and_missing_original_remain_explicit(tmp_path):
    invoice = _write(
        tmp_path,
        "case-invoice.txt",
        "ACME Sp. z o.o.\nFaktura VAT\nData: 01.10.2026\n"
        "Termin platnosci: 06.10.2026\nDo zaplaty 199,99 PLN",
    )
    letter = _write(
        tmp_path,
        "case-letter.txt",
        "Urzad Testowy\nWezwanie do zlozenia wyjasnien\nData: 02.10.2026\n"
        "Odpowiedz do 10.10.2026",
    )
    docs = [
        _indexed_document(invoice, 101, "Pilot Case"),
        _indexed_document(letter, 102, "Pilot Case"),
    ]

    preview = case_pack_preview("Pilot Case", docs)
    assert preview["document_count"] == 2
    assert preview["available_originals"] == 2
    assert preview["missing_originals"] == 0

    intact_pack = tmp_path / "pilot-case-intact.zip"
    build_case_pack(intact_pack, "Pilot Case", docs)
    intact = verify_case_pack(intact_pack)
    assert intact["valid"] is True
    assert intact["integrity"]["documents_verified"] == 2

    (tmp_path / "case-letter.txt").unlink()
    readiness = case_readiness("Pilot Case", docs, today=date(2026, 10, 4))
    assert readiness["status"] == "incomplete"
    assert readiness["counts"]["missing_originals"] == 1

    missing_preview = case_pack_preview("Pilot Case", docs)
    assert missing_preview["document_count"] == 2
    assert missing_preview["available_originals"] == 1
    assert missing_preview["missing_originals"] == 1

    incomplete_pack = tmp_path / "pilot-case-missing.zip"
    build_case_pack(incomplete_pack, "Pilot Case", docs)
    verified = verify_case_pack(incomplete_pack)
    assert verified["valid"] is True
    assert verified["integrity"]["documents_verified"] == 1
    assert verified["integrity"]["missing_originals"] == 1


def test_acceptance_manual_correction_recomputes_decision_and_records_before_after(tmp_path):
    analysis = _write(
        tmp_path,
        "uncertain-letter.txt",
        "Pismo informacyjne\nData: 01.10.2026\nTermin: 10.10.2026\n"
        "Brak informacji czego dotyczy termin.",
    )
    before = _indexed_document(analysis, 201, "Pilot Correction")
    before_decision = decision_summary(before, today=date(2026, 10, 4))
    assert before_decision["priority"] == "review"

    after = deepcopy(before)
    after["metadata"]["document_type"] = "official-letter"
    after["metadata"]["deadline"] = "2026-10-10"
    after["metadata"]["confidence"] = 0.95
    after["metadata"]["manual_verified"] = True
    after["action_required"] = "to-reply"

    after_decision = decision_summary(after, today=date(2026, 10, 4))
    changes = decision_field_changes(
        before,
        after,
        {"document_type", "deadline", "action_required"},
    )
    assert before_decision != after_decision
    assert after_decision["action_code"] == "to-reply"
    assert after_decision["due_date"] == "2026-10-10"
    assert {item["field"] for item in changes} == {
        "document_type",
        "deadline",
        "action_required",
    }
