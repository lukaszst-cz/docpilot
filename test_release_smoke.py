from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from docpilot.analyze import analyze_file


@pytest.mark.parametrize(
    ("name", "text", "expected_type", "expected_category"),
    [
        (
            "faktura.txt",
            "ACME Sp. z o.o.\nFaktura VAT nr FV/22/2026\nData: 18.09.2026\n"
            "Termin płatności: 30.09.2026\nDo zapłaty 129,99 PLN",
            "invoice",
            "Finance/Invoices",
        ),
        (
            "postanowienie.txt",
            "Sąd Rejonowy w Warszawie\nPostanowienie\nData: 21.09.2026\n"
            "Odpowiedź do 05.10.2026",
            "official-letter",
            "Official",
        ),
        (
            "umowa.txt",
            "Firma Testowa Sp. z o.o.\nUmowa o świadczenie usług zawarta dnia 01.09.2026",
            "contract",
            "Contracts",
        ),
        (
            "szkola.txt",
            "Szkoła Podstawowa nr 4\nUczeń: Jan Kowalski\nInformacja dla rodzica z dnia 15.09.2026",
            "school",
            "School",
        ),
    ],
)
def test_representative_text_documents(name, text, expected_type, expected_category, tmp_path):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")

    result = analyze_file(path)

    assert result.metadata.document_type == expected_type
    assert result.suggested_category == expected_category
    assert result.sha256
    assert result.size_bytes == path.stat().st_size
    assert result.source_path == str(path.resolve())
    assert result.suggested_filename.endswith(".txt")


def test_invoice_smoke_extracts_payment_data(tmp_path):
    path = tmp_path / "faktura-testowa.txt"
    path.write_text(
        "ACME Sp. z o.o.\nFaktura VAT nr FV/22/2026\nData: 18.09.2026\n"
        "Termin płatności: 30.09.2026\nDo zapłaty 129,99 PLN",
        encoding="utf-8",
    )

    result = analyze_file(path)

    assert result.metadata.amount == 129.99
    assert result.metadata.currency == "PLN"
    assert result.metadata.deadline.isoformat() == "2026-09-30"
    assert result.metadata.reference == "FV/22/2026"


def test_unsupported_file_is_reported_without_modifying_source(tmp_path):
    path = tmp_path / "unknown.bin"
    original = b"DocPilot smoke test"
    path.write_bytes(original)

    result = analyze_file(path)

    assert path.read_bytes() == original
    assert result.metadata.document_type == "document"
    assert any("Unsupported file type" in warning for warning in result.warnings)


def _write_text_pdf(path: Path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
    })

    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)

    with path.open("wb") as fh:
        writer.write(fh)


def test_text_pdf_is_read_and_classified(tmp_path):
    path = tmp_path / "invoice.pdf"
    _write_text_pdf(
        path,
        "Invoice number INV/2026/77 payment due 30.09.2026 amount 249.99 PLN",
    )

    result = analyze_file(path)

    assert result.metadata.document_type == "invoice"
    assert result.metadata.deadline.isoformat() == "2026-09-30"
    assert result.metadata.amount == 249.99
    assert result.metadata.currency == "PLN"
    assert "INV/2026/77" in result.extracted_text
    assert result.warnings == []
