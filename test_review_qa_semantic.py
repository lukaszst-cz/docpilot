from docpilot.qa import answer_local
from docpilot.review import build_review_queue
from docpilot.semantic import semantic_rank


def _doc(i, name, text, *, confidence=.9, health=100, action=None, amount=None, deadline=None):
    return {
        "id": i, "source_name": name, "path": f"/tmp/{name}", "extracted_text": text,
        "category": "Documents", "case_name": None, "tags": [], "health_score": health,
        "action_required": action, "sha256": str(i), "updated_at": "2026-09-19T00:00:00Z",
        "metadata": {"document_type": "document", "issuer": None, "confidence": confidence,
                     "amount": amount, "currency": "PLN" if amount is not None else None,
                     "deadline": deadline},
    }


def test_semantic_rank_returns_related_document():
    docs = [
        _doc(1, "insurance.txt", "szkoda wodna wyciek ubezpieczenie mieszkania"),
        _doc(2, "school.txt", "szkoła uczeń zajęcia matematyka"),
        _doc(3, "invoice.txt", "faktura vat płatność energia"),
        _doc(4, "vehicle.txt", "samochód polisa oc przegląd"),
    ]
    ranked = semantic_rank("zalanie mieszkania ubezpieczenie", docs, limit=4)
    assert ranked
    assert ranked[0].document["id"] == 1


def test_review_queue_flags_low_confidence_and_uncertain_deadline():
    docs = [_doc(1, "letter.txt", "Prosimy o odpowiedź do dnia wskazanego w piśmie", confidence=.4, health=55)]
    queue = build_review_queue(docs, [])
    codes = {r["code"] for r in queue[0]["reasons"]}
    assert "low-confidence" in codes
    assert "scan-health" in codes
    assert "uncertain-deadline" in codes


def test_local_qa_sums_detected_amounts():
    docs = [
        _doc(1, "a.txt", "ubezpieczenie szkoda wypłata", amount=100.0),
        _doc(2, "b.txt", "ubezpieczenie szkoda decyzja", amount=250.0),
        _doc(3, "c.txt", "szkoła zebranie", amount=None),
        _doc(4, "d.txt", "ubezpieczenie polisa", amount=None),
    ]
    answer = answer_local("ile łącznie ubezpieczenie szkoda", docs)
    assert answer["mode"] == "structured-sum"
    assert "350.00 PLN" in answer["answer"]


def test_local_qa_lists_reply_actions():
    docs = [
        _doc(1, "reply.txt", "pismo odpowiedź urząd", action="to-reply"),
        _doc(2, "archive.txt", "pismo urząd archiwum", action="to-archive"),
        _doc(3, "other.txt", "samochód", action=None),
        _doc(4, "case.txt", "urząd decyzja", action=None),
    ]
    answer = answer_local("które pisma wymagają odpowiedzi urząd", docs)
    assert "reply.txt" in answer["answer"]
