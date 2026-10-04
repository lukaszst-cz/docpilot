from datetime import date

from docpilot.lifeadmin import infer_life_context, summarize_documents


def test_vehicle_inspection_maps_to_car():
    ctx = infer_life_context("vehicle", "Przegląd techniczny pojazdu ważny do 20.11.2026")
    assert ctx["area"] == "car"
    assert ctx["event"] == "przegląd"
    assert ctx["profile"] == "Vehicle"


def test_school_document_maps_to_children():
    ctx = infer_life_context("school", "Szkoła podstawowa. Wycieczka klasy i zgoda rodzica.")
    assert ctx["area"] == "children"
    assert ctx["profile"] == "Child"


def test_receipt_return_maps_to_shopping():
    ctx = infer_life_context("receipt", "Paragon. Zwrot możliwy do 15.10.2026")
    assert ctx["area"] == "shopping"
    assert ctx["event"] == "zwrot"


def test_summary_counts_overdue_and_upcoming():
    docs = [
        {
            "id": 1,
            "source_name": "oc.pdf",
            "path": "oc.pdf",
            "action_required": "to-review",
            "metadata": {
                "document_type": "insurance",
                "life_area": "car",
                "life_event": "ubezpieczenie",
                "life_action": "Sprawdź lub odnów polisę",
                "reminder_date": "2026-10-03",
            },
        },
        {
            "id": 2,
            "source_name": "school.pdf",
            "path": "school.pdf",
            "action_required": None,
            "metadata": {
                "document_type": "school",
                "life_area": "children",
                "life_event": "wydarzenie",
                "life_action": "Dodaj wydarzenie do planu",
                "reminder_date": "2026-10-10",
            },
        },
    ]
    summary = summarize_documents(docs, today=date(2026, 10, 4))
    by_key = {item["key"]: item for item in summary["areas"]}
    assert by_key["car"]["overdue"] == 1
    assert by_key["children"]["upcoming"] == 1
    assert summary["overdue"] == 1
    assert summary["upcoming_30_days"] == 1
