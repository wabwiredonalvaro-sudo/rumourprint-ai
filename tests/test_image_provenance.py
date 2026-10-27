import io

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image
from image_provenance import analyse_image, ImageReviewError, image_report


def png_image() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (110, 120, 130)).save(buf, format="PNG")
    return buf.getvalue()


def test_provenance_image_does_not_fake_ai_percentage():
    result = analyse_image(png_image(), "photo.png")
    assert result["dimensions"] == (64, 64)
    assert result["ai_percentage"] is None
    assert result["manual_review"] is True
    assert result["finding"] != "Definitely real"
    assert "NOT MEASURABLE" in image_report(result)


def test_rejects_bogus_file():
    with pytest.raises(ImageReviewError):
        analyse_image(b"not a valid image", "photo.png")


def test_rejects_oversized_file_before_opening():
    with pytest.raises(ImageReviewError):
        analyse_image(b"x" * (8 * 1024 * 1024 + 1), "huge.jpg")


def test_requires_nonempty_image():
    with pytest.raises(ImageReviewError):
        analyse_image(b"", "empty.jpg")
