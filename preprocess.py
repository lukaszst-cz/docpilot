from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def preprocess_image(image, *, deskew: bool = True, clean: bool = True, auto_rotate: bool = True):
    """Return a cleaned PIL image plus processing notes.

    Core operations are local. Pillow is always used; OpenCV is used when the
    optional scan dependency is installed. The function never overwrites the
    source image.
    """
    from PIL import ImageEnhance, ImageFilter, ImageOps

    notes: list[str] = []
    image = ImageOps.exif_transpose(image).convert("RGB")

    if auto_rotate:
        rotated = _rotate_from_osd(image)
        if rotated is not None:
            image, degrees = rotated
            if degrees:
                notes.append(f"Auto-rotated {degrees} degrees from OCR orientation detection.")

    if deskew:
        try:
            image, angle = _deskew_opencv(image)
            if abs(angle) >= 0.15:
                notes.append(f"Deskewed by {angle:.2f} degrees.")
        except ImportError:
            notes.append("Deskew skipped: OpenCV scan extra is not installed.")
        except Exception as exc:
            notes.append(f"Deskew skipped: {exc}")

    if clean:
        gray = ImageOps.grayscale(image)
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = gray.filter(ImageFilter.MedianFilter(size=3))
        gray = ImageEnhance.Contrast(gray).enhance(1.45)
        # Conservative thresholding: retain antialiasing on already-clean pages.
        extrema = gray.getextrema()
        if extrema and extrema[1] - extrema[0] > 80:
            gray = gray.point(lambda p: 255 if p > 180 else p)
        image = gray
        notes.append("Applied grayscale, autocontrast and light denoise cleanup.")

    return image, notes


def scan_quality(image) -> dict[str, Any]:
    """Estimate scan quality without sending pixels anywhere."""
    from PIL import ImageStat, ImageOps

    gray = ImageOps.grayscale(image)
    stat = ImageStat.Stat(gray)
    mean = float(stat.mean[0]) if stat.mean else 0.0
    std = float(stat.stddev[0]) if stat.stddev else 0.0
    w, h = gray.size
    score = 100
    notes: list[str] = []
    if min(w, h) < 900:
        score -= 20
        notes.append("Low resolution for OCR.")
    if std < 24:
        score -= 25
        notes.append("Low contrast / nearly uniform page.")
    if mean < 45:
        score -= 20
        notes.append("Page is very dark.")
    elif mean > 245:
        score -= 15
        notes.append("Page is very bright / washed out.")
    return {"score": max(score, 0), "width": w, "height": h, "mean": round(mean, 1), "contrast": round(std, 1), "notes": notes}


def save_clean_copy(source: Path, destination: Path) -> tuple[Path, list[str], dict[str, Any]]:
    from PIL import Image

    with Image.open(source) as im:
        cleaned, notes = preprocess_image(im)
        quality = scan_quality(cleaned)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fmt = "PNG" if destination.suffix.lower() == ".png" else "JPEG"
        if fmt == "JPEG" and cleaned.mode not in {"RGB", "L"}:
            cleaned = cleaned.convert("RGB")
        cleaned.save(destination, format=fmt, quality=92 if fmt == "JPEG" else None)
    return destination, notes, quality


def _rotate_from_osd(image):
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        return None
    try:
        data = pytesseract.image_to_osd(image, output_type=Output.DICT)
        rotate = int(data.get("rotate") or 0) % 360
        if rotate:
            return image.rotate(-rotate, expand=True, fillcolor="white"), rotate
        return image, 0
    except Exception:
        return None


def _deskew_opencv(image):
    import cv2
    import numpy as np
    from PIL import Image

    arr = np.array(image.convert("L"))
    inv = cv2.bitwise_not(arr)
    _, thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if coords.size == 0:
        return image, 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > 20:  # avoid destructive rotation on photos/non-document images
        return image, 0.0
    h, w = arr.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        np.array(image), matrix, (w, h), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
    )
    return Image.fromarray(rotated), float(angle)
