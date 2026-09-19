import zipfile
from pathlib import Path

from docpilot.exporters import full_archive_backup


def test_full_archive_backup_includes_source_file(tmp_path: Path):
    source = tmp_path / "invoice.txt"
    source.write_text("hello", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    out = tmp_path / "backup.zip"
    docs = [{"id": 7, "source_name": source.name, "path": str(source)}]
    full_archive_backup(out, state, docs)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert any(n.startswith("source-files/7-") for n in names)
        assert "manifest.json" in names
