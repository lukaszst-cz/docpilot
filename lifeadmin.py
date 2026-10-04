from __future__ import annotations

from datetime import date
from typing import Any


LIFE_AREAS: dict[str, dict[str, str]] = {
    "car": {"label": "Samochód", "icon": "🚗", "profile": "Vehicle"},
    "home": {"label": "Dom", "icon": "🏠", "profile": "Home"},
    "children": {"label": "Dzieci", "icon": "🎒", "profile": "Child"},
    "shopping": {"label": "Zakupy", "icon": "🛍️", "profile": "Home"},
    "documents": {"label": "Dokumenty", "icon": "🪪", "profile": "Home"},
}
AREA_ORDER = ("car", "home", "children", "shopping", "documents")


def profile_for_area(area: str | None) -> str:
    return LIFE_AREAS.get(area or "documents", LIFE_AREAS["documents"])["profile"]


def infer_life_context(
    document_type: str,
    text: str,
    filename: str = "",
    *,
    deadline: Any = None,
    warranty_until: Any = None,
) -> dict[str, Any]:
    low = f"{filename}\n{text}".lower()
    scores = {key: 0 for key in AREA_ORDER}

    type_scores = {
        "vehicle": ("car", 8),
        "school": ("children", 8),
        "receipt": ("shopping", 7),
        "warranty": ("shopping", 7),
        "invoice": ("home", 2),
        "contract": ("home", 2),
        "insurance": ("home", 1),
        "official-letter": ("documents", 4),
        "document": ("documents", 1),
    }
    if document_type in type_scores:
        area, value = type_scores[document_type]
        scores[area] += value

    keyword_groups = {
        "car": (
            "samochód", "samochod", "pojazd", "dowód rejestracyjny", "dowod rejestracyjny",
            "vin", "przegląd techniczny", "przeglad techniczny", "ubezpieczenie oc", "polisa oc",
            "polisa ac", "vehicle", "registration",
        ),
        "home": (
            "mieszkanie", "dom", "nieruchomo", "czynsz", "energia", "prąd", "prad", "gaz",
            "woda", "internet", "operator", "dostawca", "administracja", "wspólnota", "wspolnota",
            "spółdziel", "spoldziel", "mortgage", "utility",
        ),
        "children": (
            "szkoła", "szkola", "uczeń", "uczen", "nauczyciel", "librus", "przedszkole",
            "wywiadówka", "wywiadowka", "zajęcia", "zajecia", "trening", "wycieczka", "kolonia",
            "school", "student", "teacher",
        ),
        "shopping": (
            "paragon", "receipt", "gwarancja", "warranty", "zwrot", "return", "reklamacja",
            "sprzęt", "sprzet", "zakup", "purchase", "sklep", "order",
        ),
        "documents": (
            "paszport", "dowód osobisty", "dowod osobisty", "prawo jazdy", "ważny do", "wazny do",
            "ważne do", "wazne do", "expires", "expiration", "urząd", "urzad", "decyzja",
        ),
    }
    for area, keywords in keyword_groups.items():
        scores[area] += sum(2 for keyword in keywords if keyword in low)

    best_area = max(AREA_ORDER, key=lambda key: scores[key])
    if scores[best_area] <= 1 and document_type not in {"vehicle", "school", "receipt", "warranty"}:
        best_area = "documents"

    event = _event_for(best_area, document_type, low)
    action = _action_for(best_area, event, deadline=deadline, warranty_until=warranty_until)
    reminder = deadline or warranty_until

    return {
        "area": best_area,
        "event": event,
        "action": action,
        "reminder_date": reminder,
        "profile": profile_for_area(best_area),
    }


def summarize_documents(documents: list[dict[str, Any]], *, today: date | None = None) -> dict[str, Any]:
    current = today or date.today()
    area_stats = {
        key: {
            "key": key,
            "label": LIFE_AREAS[key]["label"],
            "icon": LIFE_AREAS[key]["icon"],
            "count": 0,
            "open_actions": 0,
            "overdue": 0,
            "upcoming": 0,
            "next_date": None,
        }
        for key in AREA_ORDER
    }
    timeline: list[dict[str, Any]] = []

    for document in documents:
        md = document.get("metadata") or {}
        area = md.get("life_area")
        if area not in area_stats:
            inferred = infer_life_context(
                str(md.get("document_type") or "document"),
                str(document.get("extracted_text") or ""),
                str(document.get("source_name") or ""),
                deadline=md.get("deadline"),
                warranty_until=md.get("warranty_until"),
            )
            area = inferred["area"]
            event = inferred["event"]
            action = inferred["action"]
            raw_date = inferred["reminder_date"]
        else:
            event = md.get("life_event") or "document"
            action = md.get("life_action") or document.get("action_required") or "Sprawdź dokument"
            raw_date = md.get("reminder_date") or md.get("deadline") or md.get("warranty_until")

        stat = area_stats[area]
        stat["count"] += 1
        if document.get("action_required"):
            stat["open_actions"] += 1

        parsed = _as_date(raw_date)
        if parsed:
            days = (parsed - current).days
            if days < 0:
                stat["overdue"] += 1
            elif days <= 30:
                stat["upcoming"] += 1
            if stat["next_date"] is None or parsed.isoformat() < stat["next_date"]:
                stat["next_date"] = parsed.isoformat()
            timeline.append(
                {
                    "id": document.get("id"),
                    "name": document.get("source_name"),
                    "date": parsed.isoformat(),
                    "days": days,
                    "area": area,
                    "area_label": LIFE_AREAS[area]["label"],
                    "event": event,
                    "action": action,
                    "path": document.get("path"),
                }
            )

    timeline.sort(key=lambda item: (item["date"], str(item.get("name") or "")))
    return {
        "areas": [area_stats[key] for key in AREA_ORDER],
        "timeline": timeline[:40],
        "overdue": sum(item["overdue"] for item in area_stats.values()),
        "upcoming_30_days": sum(item["upcoming"] for item in area_stats.values()),
    }


def _event_for(area: str, document_type: str, low: str) -> str:
    if area == "car":
        if document_type == "insurance" or any(k in low for k in ("polisa oc", "ubezpieczenie oc", "polisa ac")):
            return "ubezpieczenie"
        if any(k in low for k in ("przegląd", "przeglad", "inspection")):
            return "przegląd"
        if any(k in low for k in ("gwarancja", "warranty")):
            return "gwarancja"
        return "dokument pojazdu"
    if area == "home":
        if document_type == "invoice" or any(k in low for k in ("rachunek", "czynsz", "energia", "gaz", "woda")):
            return "rachunek"
        if document_type == "insurance":
            return "ubezpieczenie"
        if document_type == "contract":
            return "umowa"
        return "sprawa domowa"
    if area == "children":
        if any(k in low for k in ("zajęcia", "zajecia", "trening", "kurs")):
            return "zajęcia"
        if any(k in low for k in ("wycieczka", "wydarzenie", "wywiadówka", "wywiadowka")):
            return "wydarzenie"
        return "szkoła"
    if area == "shopping":
        if any(k in low for k in ("zwrot", "return")):
            return "zwrot"
        if document_type == "warranty" or any(k in low for k in ("gwarancja", "warranty")):
            return "gwarancja"
        return "paragon"
    if any(k in low for k in ("ważny do", "wazny do", "ważne do", "wazne do", "expires", "expiration")):
        return "ważność"
    if document_type == "official-letter":
        return "pismo urzędowe"
    return "dokument"


def _action_for(area: str, event: str, *, deadline: Any = None, warranty_until: Any = None) -> str:
    if area == "car" and event == "przegląd":
        return "Umów przegląd"
    if area == "car" and event == "ubezpieczenie":
        return "Sprawdź lub odnów polisę"
    if area == "home" and event == "rachunek":
        return "Opłać rachunek"
    if area == "children" and event == "wydarzenie":
        return "Dodaj wydarzenie do planu"
    if area == "children":
        return "Sprawdź termin"
    if area == "shopping" and event == "zwrot":
        return "Zdecyduj o zwrocie"
    if area == "shopping" and event == "gwarancja":
        return "Pilnuj końca gwarancji"
    if area == "documents" and event == "ważność":
        return "Odnow dokument"
    if deadline or warranty_until:
        return "Sprawdź termin"
    return "Zachowaj i uporządkuj"


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
