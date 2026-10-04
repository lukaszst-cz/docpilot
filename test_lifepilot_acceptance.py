from datetime import date

from PIL import Image

from docpilot.analyze import analyze_file
from docpilot.lifepilot import next_action_for_document


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
