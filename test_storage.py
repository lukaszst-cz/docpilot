from pathlib import Path

from docpilot.config import get_settings
from docpilot.storage import apply_change, apply_move, undo_change


def test_move_and_undo(tmp_path: Path):
    settings = get_settings(tmp_path / "state")
    source = settings.inbox / "sample.txt"
    source.write_text("hello", encoding="utf-8")
    change = apply_move(settings, source, "Documents/Test", "renamed.txt")
    destination = Path(change.destination)
    assert destination.exists()
    assert destination.name == "renamed.txt"

    restored = undo_change(settings, change.id)
    assert restored.exists()
    assert restored == source
    assert restored.read_text(encoding="utf-8") == "hello"


def test_rename_original_in_place_and_undo(tmp_path: Path):
    settings = get_settings(tmp_path / "state")
    external = tmp_path / "user-files"
    external.mkdir()
    source = external / "scan004.txt"
    source.write_text("invoice", encoding="utf-8")

    change = apply_change(settings, source, "Finance/Invoices", "2026-09_invoice.txt", mode="rename")
    destination = Path(change.destination)

    assert not source.exists()
    assert destination.exists()
    assert destination.parent == external
    assert destination.name == "2026-09_invoice.txt"

    restored = undo_change(settings, change.id)
    assert restored == source
    assert source.exists()
    assert source.read_text(encoding="utf-8") == "invoice"


def test_windows_invalid_filename_chars_are_sanitized(tmp_path: Path):
    settings = get_settings(tmp_path / "state")
    source = tmp_path / "sample.txt"
    source.write_text("hello", encoding="utf-8")

    change = apply_change(
        settings,
        source,
        "Documents",
        '2026:09:19 invoice? <test>|.txt',
        mode="rename",
    )
    destination = Path(change.destination)
    assert destination.exists()
    assert not any(ch in destination.name for ch in '<>:"/\\|?*')
    assert change.verified is True


def test_rename_verification_and_action(tmp_path: Path):
    settings = get_settings(tmp_path / "state")
    source = tmp_path / "old.txt"
    source.write_text("abc", encoding="utf-8")
    change = apply_change(settings, source, "Documents", "new.txt", mode="rename")
    assert change.action == "rename"
    assert change.verified is True
    assert not source.exists()
    assert Path(change.destination).exists()
