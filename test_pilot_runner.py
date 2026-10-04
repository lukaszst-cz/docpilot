import json
from datetime import date

import pytest

import docpilot.pilot_runner as pilot_runner
from docpilot.pilot_runner import build_parser, run_pilot


def test_pilot_runner_writes_private_and_public_reports_without_public_leakage(tmp_path):
    source = tmp_path / "private-samples"
    output = tmp_path / "pilot-results"
    source.mkdir()
    (source / "Jan-Kowalski-secret-invoice.txt").write_text(
        "ACME Tajne Sp. z o.o.\nFaktura VAT nr FV/10/2026\n"
        "Data: 01.10.2026\nTermin platnosci: 06.10.2026\nDo zaplaty 199,99 PLN",
        encoding="utf-8",
    )
    nested = source / "sprawa-prywatna"
    nested.mkdir()
    (nested / "wezwanie-z-peselem.txt").write_text(
        "Urzad Testowy\nWezwanie do zlozenia wyjasnien\n"
        "Data: 01.10.2026\nOdpowiedz do 10.10.2026\nPESEL 44051401458",
        encoding="utf-8",
    )

    result = run_pilot(source, output, today=date(2026, 10, 4), include_private=True)
    assert result.processed == 2
    assert result.failed == 0

    private = json.loads(result.private_report.read_text(encoding="utf-8"))
    public = json.loads(result.public_report.read_text(encoding="utf-8"))
    markdown = result.markdown_report.read_text(encoding="utf-8")

    assert private["samples"][0]["relative_name"] == "Jan-Kowalski-secret-invoice.txt"
    assert private["privacy"]["publish_publicly"] is False
    assert private["samples"][0]["issuer"] == "ACME Tajne Sp. z o.o."
    assert private["samples"][0]["amount"] == 199.99

    public_text = json.dumps(public, ensure_ascii=False)
    for forbidden in (
        "Jan-Kowalski",
        "sprawa-prywatna",
        "wezwanie-z-peselem",
        "ACME Tajne",
        "Urzad Testowy",
        "199.99",
        "44051401458",
        str(source),
        "FV/10/2026",
    ):
        assert forbidden not in public_text
        assert forbidden not in markdown

    assert public["samples"][0]["sample_id"] == "S001"
    assert public["samples"][0]["has_amount"] is True
    assert public["samples"][0]["has_deadline"] is True
    assert public["privacy"]["contains_filenames"] is False
    assert public["privacy"]["contains_extracted_text"] is False
    assert "Ręczna akceptacja" in markdown


def test_pilot_runner_is_deterministic_and_ignores_unsupported_files(tmp_path):
    source = tmp_path / "samples"
    output = tmp_path / "results"
    source.mkdir()
    (source / "B.txt").write_text("Notatka B bez terminu.", encoding="utf-8")
    (source / "a.txt").write_text("Notatka A bez terminu.", encoding="utf-8")
    (source / "ignored.exe").write_bytes(b"not a document")

    run_pilot(source, output, today=date(2026, 10, 4), include_private=True)
    private = json.loads((output / "pilot-private.json").read_text(encoding="utf-8"))

    assert [item["relative_name"] for item in private["samples"]] == ["a.txt", "B.txt"]
    assert [item["sample_id"] for item in private["samples"]] == ["S001", "S002"]


def test_pilot_runner_rejects_output_inside_source(tmp_path):
    source = tmp_path / "samples"
    source.mkdir()
    with pytest.raises(ValueError, match="outside the source directory"):
        run_pilot(source, source / "results", today=date(2026, 10, 4))


def test_pilot_runner_does_not_write_private_report_by_default(tmp_path):
    source = tmp_path / "samples-default"
    output = tmp_path / "results-default"
    source.mkdir()
    (source / "sensitive-name.txt").write_text(
        "ACME Secret\nFaktura VAT\nTermin platnosci: 06.10.2026\nDo zaplaty 123,45 PLN",
        encoding="utf-8",
    )

    result = run_pilot(source, output, today=date(2026, 10, 4))

    assert result.private_report is None
    assert not (output / "pilot-private.json").exists()
    assert (output / "pilot-public.json").exists()
    assert (output / "pilot-report.md").exists()


def test_pilot_parser_allows_windows_launcher_without_source():
    args = build_parser().parse_args([])
    assert args.source_dir is None
    assert args.output is None
    assert args.include_private is False


def test_default_windows_output_uses_local_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    output = pilot_runner._default_windows_output_dir()

    assert output.parent.name == "PilotResults"
    assert output.is_relative_to(tmp_path / "LocalAppData" / "DocPilot" / "PilotResults")


def test_windows_launcher_picker_runs_public_safe_pilot(monkeypatch, tmp_path):
    source = tmp_path / "selected-documents"
    output = tmp_path / "local-app-data" / "DocPilot" / "PilotResults" / "test-run"
    source.mkdir()
    (source / "private-invoice.txt").write_text(
        "ACME Secret\nFaktura VAT\nTermin platnosci: 06.10.2026\nDo zaplaty 123,45 PLN",
        encoding="utf-8",
    )
    shown = []

    monkeypatch.setattr(pilot_runner.sys, "platform", "win32")
    monkeypatch.setattr(pilot_runner, "_pick_windows_source_dir", lambda: source)
    monkeypatch.setattr(pilot_runner, "_default_windows_output_dir", lambda: output)
    monkeypatch.setattr(pilot_runner, "_show_windows_result", lambda result: shown.append(result))

    exit_code = pilot_runner.main([])

    assert exit_code == 0
    assert shown and shown[0].processed == 1
    assert (output / "pilot-public.json").exists()
    assert (output / "pilot-report.md").exists()
    assert not (output / "pilot-private.json").exists()
