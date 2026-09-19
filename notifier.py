from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

from .config import get_settings
from .db import get_setting, list_documents, set_setting

TASK_NAME = "DocPilot Deadline Notifications"


def collect_due(days_ahead: int = 3) -> list[dict]:
    settings = get_settings()
    today = date.today()
    out = []
    for d in list_documents(settings, 5000):
        md = d.get("metadata") or {}
        raw = md.get("deadline") or md.get("warranty_until")
        if not raw:
            continue
        try:
            day = date.fromisoformat(str(raw))
        except ValueError:
            continue
        delta = (day - today).days
        if -1 <= delta <= days_ahead:
            out.append({"id": d.get("id"), "name": d.get("source_name"), "date": day.isoformat(), "days": delta, "action": d.get("action_required")})
    return sorted(out, key=lambda x: x["date"])


def notify_once(days_ahead: int = 3) -> int:
    settings = get_settings()
    due = collect_due(days_ahead)
    today_key = date.today().isoformat()
    shown = 0
    for item in due:
        key = f"notify:{today_key}:{item['id']}:{item['date']}"
        if get_setting(settings, key):
            continue
        if item["days"] < 0:
            when = "overdue"
        elif item["days"] == 0:
            when = "today"
        else:
            when = f"in {item['days']} day(s)"
        _toast("DocPilot deadline", f"{item['name']} — {when} ({item['date']})")
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
            notify_once(max(0, min(configured, 30)))
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
