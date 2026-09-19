from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from docpilot.app import _save_upload_with_limit


def test_upload_is_stopped_and_removed_when_limit_is_exceeded(tmp_path: Path):
    destination = tmp_path / "too-large.bin"
    upload = UploadFile(filename="too-large.bin", file=BytesIO(b"x" * 12))

    with pytest.raises(HTTPException) as exc:
        _save_upload_with_limit(upload, destination, max_bytes=8)

    assert exc.value.status_code == 413
    assert not destination.exists()


def test_upload_within_limit_is_saved(tmp_path: Path):
    destination = tmp_path / "ok.bin"
    upload = UploadFile(filename="ok.bin", file=BytesIO(b"12345678"))

    written = _save_upload_with_limit(upload, destination, max_bytes=8)

    assert written == 8
    assert destination.read_bytes() == b"12345678"
