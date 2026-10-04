from docpilot.exporters import ics_for_documents


def _doc(deadline: str, *, doc_id: int, source_name: str, path: str):
    return {
        "id": doc_id,
        "source_name": source_name,
        "path": path,
        "action_required": "to-reply",
        "metadata": {"deadline": deadline},
    }


def test_ics_uses_timezone_independent_all_day_dates_across_polish_dst_boundaries():
    ics = ics_for_documents(
        [
            _doc(
                "2026-03-29",
                doc_id=1,
                source_name="wiosna.txt",
                path=r"C:\\Users\\Private\\secret-spring.txt",
            ),
            _doc(
                "2026-10-25",
                doc_id=2,
                source_name="jesien.txt",
                path=r"C:\\Users\\Private\\secret-autumn.txt",
            ),
        ]
    )

    assert "DTSTART;VALUE=DATE:20260329" in ics
    assert "DTEND;VALUE=DATE:20260330" in ics
    assert "DTSTART;VALUE=DATE:20261025" in ics
    assert "DTEND;VALUE=DATE:20261026" in ics
    assert "TZID=" not in ics
    assert "Z:" not in ics


def test_ics_does_not_expose_local_file_path():
    secret_path = r"C:\\Users\\Lukasz\\Documents\\private-case\\secret.pdf"
    ics = ics_for_documents(
        [_doc("2026-10-10", doc_id=7, source_name="secret.pdf", path=secret_path)]
    )

    assert secret_path not in ics
    assert "private-case" not in ics
    assert "DESCRIPTION:Termin z LifePilot." in ics
    assert "SUMMARY:DocPilot: to-pay" not in ics
    assert "SUMMARY:DocPilot: to-reply" in ics
