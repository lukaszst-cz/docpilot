from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

from pypdf import PdfReader

from .preprocess import preprocess_image

_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log", ".xml", ".html"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def extract_text(path: Path) -> tuple[str, list[str]]:
    suffix = path.suffix.lower()
    warnings: list[str] = []

    if suffix == ".pdf":
        try:
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            text = ""
            warnings.append(f"PDF text-layer extraction failed: {exc}")

        if len(text.strip()) < 25:
            warnings.append("PDF contains little or no searchable text; local page OCR was attempted.")
            try:
                ocr_text, ocr_notes = _ocr_pdf(path)
                if ocr_text.strip():
                    text = ocr_text
                warnings.extend(ocr_notes)
            except ImportError:
                warnings.append("Scanned-PDF OCR requires the full scan dependencies (PDFium + Tesseract).")
            except Exception as exc:
                warnings.append(f"Scanned-PDF OCR failed: {exc}")
        return _clean(text), list(dict.fromkeys(warnings))

    if suffix in _TEXT_EXTENSIONS:
        try:
            return _clean(path.read_text(encoding="utf-8", errors="ignore")), warnings
        except Exception as exc:
            return "", [f"Text extraction failed: {exc}"]

    if suffix in _IMAGE_EXTENSIONS:
        try:
            import pytesseract
            from PIL import Image
            _configure_tesseract(pytesseract)

            with Image.open(path) as src:
                image, notes = preprocess_image(src)
                text = pytesseract.image_to_string(image, lang=_ocr_languages())
            warnings.extend(notes)
            if not text.strip():
                warnings.append("OCR returned no text.")
            barcode_text = _extract_barcodes(path)
            if barcode_text:
                text = f"{text}\n\n[BARCODES]\n{barcode_text}"
            return _clean(text), list(dict.fromkeys(warnings))
        except ImportError:
            warnings.append("OCR is optional. Install DocPilot with the scan/full extra and Tesseract.")
            return "", warnings
        except Exception as exc:
            warnings.append(f"OCR failed: {exc}")
            return "", warnings

    warnings.append(f"Unsupported file type: {suffix or 'no extension'}")
    return "", warnings


def _ocr_pdf(path: Path) -> tuple[str, list[str]]:
    import pypdfium2 as pdfium
    import pytesseract

    _configure_tesseract(pytesseract)
    notes: list[str] = []
    pages: list[str] = []
    pdf = pdfium.PdfDocument(str(path))
    max_pages = min(len(pdf), 80)
    if len(pdf) > max_pages:
        notes.append(f"OCR limited to the first {max_pages} pages.")
    for i in range(max_pages):
        page = pdf[i]
        image = page.render(scale=1.7).to_pil()
        cleaned, page_notes = preprocess_image(image)
        text = pytesseract.image_to_string(cleaned, lang=_ocr_languages())
        if text.strip():
            pages.append(f"[PAGE {i+1}]\n{text}")
        if i == 0:
            notes.extend(page_notes)
    return "\n\n".join(pages), list(dict.fromkeys(notes))


def _configure_tesseract(pytesseract_module) -> None:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "tesseract" / "tesseract.exe")
    candidates += [
        Path.cwd() / "tesseract" / "tesseract.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR" / "tesseract.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(candidate)
            tessdata = candidate.parent / "tessdata"
            if tessdata.exists():
                os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))
            return


def _ocr_languages() -> str:
    return "pol+eng"


def _extract_barcodes(path: Path) -> str:
    values = []
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode
        with Image.open(path) as im:
            for code in decode(im):
                try:
                    value = code.data.decode("utf-8", errors="replace")
                except Exception:
                    value = repr(code.data)
                values.append(f"{code.type}: {value}")
    except Exception:
        pass
    if not values:
        # OpenCV is part of the scan bundle and can decode QR without an extra
        # system zbar DLL. Traditional 1D barcodes still use optional pyzbar.
        try:
            import cv2
            image = cv2.imread(str(path))
            detector = cv2.QRCodeDetector()
            ok, decoded, _, _ = detector.detectAndDecodeMulti(image)
            if ok:
                values.extend(f"QR: {value}" for value in decoded if value)
            else:
                value, _, _ = detector.detectAndDecode(image)
                if value:
                    values.append(f"QR: {value}")
        except Exception:
            pass
    return "\n".join(values)


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
