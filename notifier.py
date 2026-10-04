from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

from .config import get_settings
from .db import get_setting, list_documents, set_setting
from .lifepilot import attention_signature, handled_entry_matches, lifepilot_queue

TASK_NAME = "DocPilot Deadline Notifications"


def _handled_map(settings) -> dict[str, object]:
    raw = get_setting(settings, "lifepilot.done", "{}") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def collect_notification_items(
    documents: list[dict],
    handled: dict[str, object] | None = None,
    *,
    days_ahead: int = 3,
    today: date | None = None,
) -> list[dict]:
    today = today or date.today()
    horizon = max(0, min(int(days_ahead), 30))
    handled = handled or {}
    by_id = {int(doc.get("id")): doc for doc in documents if doc.get("id") is not None}
    items: list[dict] = []

    for item in lifepilot_queue(documents, today=today, limit=5000):
        doc_id = int(item.get("id") or 0)
        document = by_id.get(doc_id)
        if not document:
            continue
        if handled_entry_matches(handled.get(str(doc_id)), document):
            continue

        next_action = item.get("next_action") or {}
        days = next_action.get("days_remaining")
        due_date = next_action.get("due_date")
        if days is None or not due_date:
            continue
        if int(days) < -7 or int(days) > horizon:
            continue

        items.append(
            {
                "id": doc_id,
                "name": item.get("source_name"),
                "date": due_date,
                "days": int(days),
                "action": item.get("action_required"),
                "title": next_action.get("title") or "Sprawdź dokument",
                "priority": next_action.get("priority") or "normal",
                "verification": next_action.get("verification") or {},
                "signature": attention_signature(document),
            }
        )
    return items


def collect_due(days_ahead: int = 3, *, settings=None, today: date | None = None) -> list[dict]:
    settings = settings or get_settings()
    documents = list_documents(settings, 5000)
    return collect_notification_items(
        documents,
        _handled_map(settings),
        days_ahead=days_ahead,
        today=today,
    )


def notify_once(days_ahead: int = 3, *, settings=None, today: date | None = None) -> int:
    settings = settings or get_settings()
    today = today or date.today()
    due = collect_due(days_ahead, settings=settings, today=today)
    today_key = today.isoformat()
    shown = 0
    for item in due:
        signature = str(item.get("signature") or "")[:16]
        key = f"notify:{today_key}:{item['id']}:{item['date']}:{signature}"
        if get_setting(settings, key):
            continue
        if item["days"] < 0:
            when = f"{abs(item['days'])} day(s) overdue"
        elif item["days"] == 0:
            when = "today"
        else:
            when = f"in {item['days']} day(s)"
        _toast(
            "LifePilot · Co teraz?",
            f"{item['name']} — {item['title']} · {when} ({item['date']})",
        )
        set_setting(settings, key, datetime.now().isoformat())
        shown += 1
    return shown


def _toast(title: str, message: str) -> None:
    if os.name == "nt":
        try:
            from winotify import Notification
            Notification(app_id="DocPilot", title=title, msg=message, duration="short").show()
            return
        except Exception:
            pass
    print(f"{title}: {message}")


def install_startup(executable: str | None = None) -> None:
    if os.name != "nt":
        raise RuntimeError("Automatic startup registration is currently implemented for Windows.")
    exe = executable or sys.executable
    if getattr(sys, "frozen", False):
        command = f'"{exe}" --run'
    else:
        command = f'"{exe}" -m docpilot.notifier --run'
    subprocess.run(["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", TASK_NAME, "/TR", command], check=True, capture_output=True)


def remove_startup() -> None:
    if os.name == "nt":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=False, capture_output=True)


def run_loop(interval_minutes: int = 30, days_ahead: int = 3) -> None:
    settings = get_settings()
    while True:
        try:
            configured = int(get_setting(settings, "notification_days", str(days_ahead)) or days_ahead)
            notify_once(max(0, min(configured, 30)), settings=settings)
        except Exception:
            pass
        time.sleep(max(5, interval_minutes) * 60)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--install-startup", action="store_true")
    parser.add_argument("--remove-startup", action="store_true")
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    if args.install_startup:
        install_startup()
        return
    if args.remove_startup:
        remove_startup()
        return
    if args.once:
        notify_once(args.days)
        return
    run_loop(days_ahead=args.days)


if __name__ == "__main__":
    main()
