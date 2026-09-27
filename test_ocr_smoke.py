from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from docpilot.extract import extract_text, _configure_tesseract


pytesseract = pytest.importorskip("pytesseract")


def _ocr_available() -> bool:
    try:
        _configure_tesseract(pytesseract)
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _ocr_available(), reason="Tesseract is not available in this environment")
def test_real_png_ocr_smoke(tmp_path: Path):
    image = Image.new("RGB", (1400, 320), "white")
    draw = ImageDraw.Draw(image)

    font_path = Path("C:/Windows/Fonts/arial.ttf")
    if not font_path.exists():
        font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 58) if font_path.exists() else ImageFont.load_default()

    draw.text((60, 80), "INVOICE TOTAL 249.99 PLN", fill="black", font=font)
    path = tmp_path / "invoice.png"
    image.save(path)

    text, warnings = extract_text(path)
    normalized = text.upper()

    assert "INVOICE" in normalized
    assert "249" in normalized
    assert not any("OCR FAILED" in warning.upper() for warning in warnings)


@pytest.mark.skipif(not _ocr_available(), reason="Tesseract is not available in this environment")
def test_scanned_pdf_ocr_smoke(tmp_path: Path):
    pytest.importorskip("pypdfium2")

    image = Image.new("RGB", (1400, 500), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    if not font_path.exists():
        font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 58) if font_path.exists() else ImageFont.load_default()

    draw.text((70, 150), "SCANNED INVOICE 349.99 PLN", fill="black", font=font)
    path = tmp_path / "scanned-invoice.pdf"
    image.save(path, "PDF", resolution=150.0)

    text, warnings = extract_text(path)
    normalized = text.upper()

    assert "SCANNED" in normalized
    assert "349" in normalized
    assert any("OCR" in warning.upper() for warning in warnings)
    assert not any("OCR FAILED" in warning.upper() for warning in warnings)
