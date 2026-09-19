from __future__ import annotations

import io
from pathlib import Path

from .intelligence import detect_sensitive, redact_text


def redact_file(source: Path, destination: Path, extracted_text: str = "") -> tuple[Path, list[dict[str, str]], list[str]]:
    suffix = source.suffix.lower()
    warnings: list[str] = []
    if suffix in {".txt", ".md", ".csv", ".json", ".log", ".xml", ".html"}:
        text = source.read_text(encoding="utf-8", errors="ignore")
        redacted, found = redact_text(text)
        destination.write_text(redacted, encoding="utf-8")
        return destination, found, warnings

    if suffix == ".pdf":
        output, found = _redact_pdf_raster(source, destination)
        warnings.append("PDF was rasterized and redacted from OCR coordinates. Review the copy before sharing.")
        return output, found, warnings

    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        from PIL import Image
        with Image.open(source) as im:
            image, found = _redact_image_ocr(im.convert("RGB"))
            image.save(destination)
        warnings.append("Image redaction is OCR-coordinate based; review the output before sharing.")
        return destination, found, warnings

    redacted, found = redact_text(extracted_text)
    destination = destination.with_suffix(destination.suffix + ".redacted.txt")
    destination.write_text(redacted, encoding="utf-8")
    warnings.append("Original format redaction is not supported; a redacted text export was created.")
    return destination, found, warnings


def _redact_pdf_raster(source: Path, destination: Path):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(source))
    images = []
    all_found: list[dict[str, str]] = []
    for i in range(len(pdf)):
        page = pdf[i]
        image = page.render(scale=1.8).to_pil().convert("RGB")
        redacted, found = _redact_image_ocr(image)
        images.append(redacted)
        all_found.extend(found)
    if not images:
        raise RuntimeError("PDF has no pages.")
    first, rest = images[0], images[1:]
    first.save(destination, "PDF", save_all=True, append_images=rest, resolution=150.0)
    return destination, _dedupe(all_found)


def _redact_image_ocr(image):
    import pytesseract
    from PIL import ImageDraw

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang="pol+eng")
    draw = ImageDraw.Draw(image)
    groups: dict[tuple[int, int, int], list[int]] = {}
    for i, token in enumerate(data.get("text", [])):
        if not str(token).strip():
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        groups.setdefault(key, []).append(i)

    found_all: list[dict[str, str]] = []
    for indices in groups.values():
        tokens = [str(data["text"][i]) for i in indices]
        line = " ".join(tokens)
        found = detect_sensitive(line)
        found_all.extend(found)
        if not found:
            continue
        # Map character spans in the reconstructed line back to OCR token boxes.
        offsets = []
        pos = 0
        for token, idx in zip(tokens, indices):
            start = pos
            end = start + len(token)
            offsets.append((start, end, idx))
            pos = end + 1
        for item in found:
            needle = item["value"]
            start = line.find(needle)
            if start < 0:
                compact = needle.replace(" ", "")
                # Conservative fallback: redact tokens that appear in the PII value.
                chosen = [idx for token, idx in zip(tokens, indices) if token and token.replace(" ", "") in compact]
            else:
                end = start + len(needle)
                chosen = [idx for a, b, idx in offsets if a < end and b > start]
            if not chosen:
                continue
            left = min(int(data["left"][i]) for i in chosen)
            top = min(int(data["top"][i]) for i in chosen)
            right = max(int(data["left"][i]) + int(data["width"][i]) for i in chosen)
            bottom = max(int(data["top"][i]) + int(data["height"][i]) for i in chosen)
            pad = 3
            draw.rectangle((max(0,left-pad), max(0,top-pad), right+pad, bottom+pad), fill="black")
    return image, _dedupe(found_all)


def _dedupe(items):
    seen = set()
    out = []
    for item in items:
        key = (item.get("type"), item.get("value"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
