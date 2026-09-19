from docpilot.analyze import infer_metadata


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
