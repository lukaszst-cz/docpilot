import docpilot.analyze as analyze_module
from docpilot.analyze import analyze_file, infer_metadata


def test_invoice_deadline_and_amount():
    text = """ACME Sp. z o.o.\nFaktura VAT nr FV/22/2026\nData: 18.09.2026\nTermin płatności: 30.09.2026\nDo zapłaty 129,99 PLN"""
    meta = infer_metadata(text)
    assert meta.document_type == "invoice"
    assert meta.amount == 129.99
    assert meta.currency == "PLN"
    assert meta.deadline.isoformat() == "2026-09-30"
    assert meta.reference == "FV/22/2026"


def test_contract_detection():
    meta = infer_metadata("Umowa o świadczenie usług zawarta dnia 01.09.2026")
    assert meta.document_type == "contract"


def test_contract_reference_date_is_not_swapped():
    meta = infer_metadata(
        "Umowa o swiadczenie uslug\n"
        "Nr umowy: TEST/2026/10/01\n"
        "Data zawarcia: 01.10.2026"
    )
    assert meta.document_date.isoformat() == "2026-10-01"
    assert meta.reference == "TEST/2026/10/01"


def test_relative_deadline_uses_explicit_delivery_date():
    meta = infer_metadata(
        "Urzad Testowy\n"
        "Wezwanie do uzupelnienia brakow\n"
        "W terminie 7 dni od dnia doreczenia pisma.\n"
        "Data doreczenia: 03.10.2026"
    )
    assert meta.deadline.isoformat() == "2026-10-10"


def test_generic_do_date_is_treated_as_deadline():
    meta = infer_metadata(
        "Ubezpieczyciel Test SA\n"
        "Prosba o uzupelnienie dokumentow szkody.\n"
        "Prosze o doslanie kosztorysu naprawy do 13.10.2026."
    )
    assert meta.deadline.isoformat() == "2026-10-13"


def test_relative_deadline_without_delivery_date_is_not_guessed():
    meta = infer_metadata(
        "Pismo informacyjne\n"
        "Data: 03.10.2026\n"
        "Odpowiedz nalezy przeslac w ciagu 15 dni od doreczenia.\n"
        "Data doreczenia nie jest podana."
    )
    assert meta.deadline is None


def test_school_consent_deadline_keeps_sign_action(tmp_path):
    path = tmp_path / "school.txt"
    path.write_text(
        "Szkola Podstawowa Testowa\n"
        "Prosze przekazac podpisana zgode do 09.10.2026.\n"
        "Koszt 45,00 PLN.",
        encoding="utf-8",
    )
    analysis = analyze_file(path)
    assert analysis.metadata.deadline.isoformat() == "2026-10-09"
    assert analysis.action_required == "to-sign"


def test_insurance_request_with_do_date_becomes_reply_action(tmp_path):
    path = tmp_path / "insurance.txt"
    path.write_text(
        "Ubezpieczyciel Test SA\n"
        "Szkoda REF-TEST-4421\n"
        "Prosze o doslanie kosztorysu do 13.10.2026.",
        encoding="utf-8",
    )
    analysis = analyze_file(path)
    assert analysis.metadata.deadline.isoformat() == "2026-10-13"
    assert analysis.action_required == "to-reply"


def test_low_health_ocr_caps_confidence_for_review(monkeypatch, tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"synthetic")
    monkeypatch.setattr(
        analyze_module,
        "extract_text",
        lambda _: (
            "Faktura VAT\nData: 02.10.2026\nTermin platnosci: 08.10.2026\n"
            "Do zaplaty 317,40 PLN",
            [
                "PDF contains little or no searchable text; local page OCR was attempted.",
                "Deskewed by -1.57 degrees.",
                "Applied grayscale, autocontrast and light denoise cleanup.",
            ],
        ),
    )
    analysis = analyze_module.analyze_file(path)
    assert analysis.health_score == 70
    assert analysis.metadata.confidence < 0.65


def test_total_amount_is_preferred_over_first_line_item(tmp_path):
    path = tmp_path / "estimate.txt"
    path.write_text(
        "Kosztorys naprawy\n"
        "Pozycja 1: materialy - 620,00 PLN\n"
        "Pozycja 2: robocizna - 850,00 PLN\n"
        "Lacznie: 1 470,00 PLN",
        encoding="utf-8",
    )
    analysis = analyze_file(path)
    assert analysis.metadata.amount == 1470.00
