from pathlib import Path

from docpilot.config import get_settings
from docpilot.storage import apply_move, archive_root_for_profile, undo_change


def _source(settings, name: str, content: str = "document") -> Path:
    path = settings.inbox / name
    path.write_text(content, encoding="utf-8")
    return path


def test_home_profile_keeps_legacy_archive_layout(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    source = _source(settings, "home.txt")

    change = apply_move(
        settings,
        source,
        "Finance/Invoices",
        "invoice.txt",
        profile="Home",
    )

    destination = Path(change.destination)
    assert destination.parent == (settings.archive / "Finance" / "Invoices").resolve()
    assert "Profiles" not in destination.parts


def test_non_home_profiles_use_separate_archive_spaces(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    company_source = _source(settings, "company-source.txt", "company")
    child_source = _source(settings, "child-source.txt", "child")

    company = apply_move(
        settings,
        company_source,
        "Documents",
        "shared-name.txt",
        profile="Company",
    )
    child = apply_move(
        settings,
        child_source,
        "Documents",
        "shared-name.txt",
        profile="Child",
    )

    company_path = Path(company.destination)
    child_path = Path(child.destination)

    assert company_path.parent == (settings.archive / "Profiles" / "Company" / "Documents").resolve()
    assert child_path.parent == (settings.archive / "Profiles" / "Child" / "Documents").resolve()
    assert company_path.name == "shared-name.txt"
    assert child_path.name == "shared-name.txt"
    assert company_path != child_path


def test_profile_space_name_is_sanitized_inside_archive(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    root = archive_root_for_profile(settings, "../../Company:Legal?")

    profiles_root = (settings.archive / "Profiles").resolve()
    resolved = root.resolve()

    assert resolved.parent == profiles_root
    assert resolved != settings.archive.resolve()
    assert ".." not in resolved.parts
    assert ":" not in resolved.name
    assert "?" not in resolved.name


def test_profile_space_move_keeps_undo_working(tmp_path):
    settings = get_settings(tmp_path / "DocPilotData")
    source = _source(settings, "legal-source.txt", "important")

    change = apply_move(
        settings,
        source,
        "Court/Letters",
        "letter.txt",
        profile="Legal Cases",
    )
    destination = Path(change.destination)
    assert destination.exists()
    assert destination.parent == (
        settings.archive / "Profiles" / "Legal Cases" / "Court" / "Letters"
    ).resolve()

    restored = undo_change(settings, change.id)

    assert restored == source
    assert restored.exists()
    assert restored.read_text(encoding="utf-8") == "important"
    assert not destination.exists()
