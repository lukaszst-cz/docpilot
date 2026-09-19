from PIL import Image

from docpilot.preprocess import preprocess_image, scan_quality


def test_preprocess_and_quality_return_image_and_score():
    image = Image.new("RGB", (1200, 1600), "white")
    cleaned, notes = preprocess_image(image, deskew=False, auto_rotate=False)
    quality = scan_quality(cleaned)
    assert cleaned.size == image.size
    assert 0 <= quality["score"] <= 100
    assert notes
