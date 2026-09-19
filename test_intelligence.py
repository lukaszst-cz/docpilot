from pathlib import Path

from docpilot.analyze import analyze_file
from docpilot.intelligence import detect_sensitive, hamming_hex, language_detect, redact_text, simhash64


def test_sensitive_detection_and_redaction():
    text = "PESEL 44051401458, email test@example.com, IBAN PL61109010140000071219812874"
    found = detect_sensitive(text)
    kinds = {x["type"] for x in found}
    assert "PESEL" in kinds
    assert "email" in kinds
    assert "IBAN" in kinds
    redacted, _ = redact_text(text)
    assert "44051401458" not in redacted
    assert "test@example.com" not in redacted


def test_language_and_simhash():
    assert language_detect("To jest faktura oraz termin płatności i kwota") == "pl"
    a = simhash64("invoice orange payment due tomorrow")
    b = simhash64("invoice orange payment due tomorrow")
    assert hamming_hex(a, b) == 0


def test_invoice_enrichment(tmp_path: Path):
    p = tmp_path / "invoice.txt"
    p.write_text(
        "ACME Sp. z o.o.\nFaktura nr FV/12/2026\nData 19.09.2026\nTermin płatności 30.09.2026\n"
        "NIP 123-456-32-18\nIBAN PL61109010140000071219812874\nDo zapłaty 249,99 PLN\nVAT 23%",
        encoding="utf-8",
    )
    a = analyze_file(p)
    assert a.metadata.document_type == "invoice"
    assert a.metadata.deadline.isoformat() == "2026-09-30"
    assert a.metadata.invoice_number
    assert a.action_required == "to-pay"
    assert "finance" in a.tags
