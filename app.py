from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .analyze import analyze_file
from .config import get_settings
from .db import (
    add_custom_type,
    add_rule,
    audit,
    delete_document_by_path,
    duplicate_groups,
    get_document,
    get_setting,
    init_db,
    list_audit,
    list_custom_types,
    list_documents,
    list_rules,
    search_documents,
    set_setting,
    update_document_fields,
    upsert_document,
)
from .diffing import compare_documents
from .exporters import backup_zip, full_archive_backup, ics_for_documents, notion_csv, obsidian_zip
from .semantic import semantic_rank
from .qa import answer_local
from .review import build_review_queue
from .preprocess import save_clean_copy
from .integrations import (
    configure_google_calendar, configure_imap, configure_notion, google_calendar_status,
    imap_status, import_imap_attachments, notion_status, sync_google_calendar, sync_notion,
)
from .notifier import install_startup as install_notifier_startup, remove_startup as remove_notifier_startup, notify_once
from .models import ApplyRequest
from .redaction import redact_file
from .rules import apply_rules
from .storage import apply_change, list_changes, safe_name, undo_change, unique_destination

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates" if (BASE_DIR / "templates").exists() else BASE_DIR
PACKAGED_STATIC_DIR = BASE_DIR / "static"
STATIC_DIR = PACKAGED_STATIC_DIR if PACKAGED_STATIC_DIR.exists() else BASE_DIR
DEMO_DIR = BASE_DIR / "demo" if (BASE_DIR / "demo").exists() else BASE_DIR

settings = get_settings()
init_db(settings)

LOG_PATH = Path.cwd() / "docpilot.log"
logger = logging.getLogger("docpilot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

app = FastAPI(title="DocPilot", version=__version__)

if PACKAGED_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    _SOURCE_STATIC_FILES = {"app.css", "app.js", "icon-192.png", "icon-512.png"}

    @app.get("/static/{filename}")
    def source_static(filename: str):
        if filename not in _SOURCE_STATIC_FILES:
            raise HTTPException(404, "Static file not found")
        return FileResponse(BASE_DIR / filename)


def _local_origin_allowed(origin: str) -> bool:
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


@app.middleware("http")
async def local_browser_guard(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and not _local_origin_allowed(origin):
        return JSONResponse(status_code=403, content={"detail": "Cross-origin request blocked."})
    return await call_next(request)


WATCHER_STOP = threading.Event()
WATCHER_THREAD: threading.Thread | None = None


@app.get("/")
def index():
    return FileResponse(
        TEMPLATE_DIR / "index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js")
def service_worker():
    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "local-first", "version": __version__, "pwa": True, "review_queue": True, "background_notifications": True}


def _demo_source_path() -> Path:
    candidates = [
        DEMO_DIR / "sample_invoice.txt",
        BASE_DIR / "sample_invoice.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Bundled demo document is missing.")


@app.post("/api/demo")
def load_safe_demo():
    source = _demo_source_path()
    destination = unique_destination(settings.inbox, "DocPilot-demo-invoice.txt")
    shutil.copy2(source, destination)
    data = _analyze_and_index(destination, profile="Home")
    data["source_mode"] = "demo"
    audit(settings, "demo-loaded", {"path": str(destination), "id": data["id"]})
    return data


def _pick_file_windows(title: str = "Select a document for DocPilot") -> str | None:
    safe_title = title.replace("'", "''")
    script = rf"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(1,1)
$owner.Opacity = 0
$owner.Show()
$owner.Activate()
[System.Windows.Forms.Application]::DoEvents()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '{safe_title}'
$dialog.Filter = 'Documents and images|*.pdf;*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff;*.bmp;*.txt;*.md;*.csv;*.json;*.eml|All files|*.*'
$dialog.Multiselect = $false
$dialog.RestoreDirectory = $true
$result = $dialog.ShowDialog($owner)
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}}
$owner.Close(); $owner.Dispose()
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows file picker failed")
    return result.stdout.strip() or None


def _pick_folder_windows(title: str = "Select a folder for DocPilot") -> str | None:
    safe_title = title.replace("'", "''")
    script = rf"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '{safe_title}'
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows folder picker failed")
    return result.stdout.strip() or None


def _pick_file_fallback(title: str = "Select a document for DocPilot") -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    value = filedialog.askopenfilename(title=title)
    root.destroy()
    return value or None


def _pick_folder_fallback(title: str = "Select a folder for DocPilot") -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    value = filedialog.askdirectory(title=title)
    root.destroy()
    return value or None


def _analyze_and_index(path: Path, *, profile: str = "Home") -> dict[str, Any]:
    custom_types = list_custom_types(settings)
    analysis = analyze_file(path, custom_types=custom_types)
    doc = {
        "metadata": analysis.metadata.model_dump(mode="json"),
        "category": analysis.suggested_category,
        "profile": profile,
        "tags": analysis.tags,
        "extracted_text": analysis.extracted_text,
    }
    ruled = apply_rules(doc, list_rules(settings))
    analysis.suggested_category = ruled["category"] or analysis.suggested_category
    analysis.tags = ruled["tags"]
    doc_id = upsert_document(
        settings,
        analysis,
        profile=ruled["profile"] or profile,
        case_name=analysis.suggested_case,
        tags=analysis.tags,
        action_required=analysis.action_required,
        health_score=analysis.health_score,
        health=analysis.health_notes,
        simhash=analysis.simhash,
    )
    data = analysis.model_dump(mode="json")
    data["id"] = doc_id
    data["profile"] = ruled["profile"] or profile
    return data


@app.post("/api/select-local")
def select_local():
    try:
        selected = _pick_file_windows() if os.name == "nt" else _pick_file_fallback()
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not selected:
        return {"cancelled": True}
    path = Path(selected).resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Selected file does not exist")
    if path.stat().st_size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
    data = _analyze_and_index(path)
    data["source_mode"] = "original"
    audit(settings, "analyzed", {"path": str(path), "id": data["id"]})
    return data


def _save_upload_with_limit(upload: UploadFile, destination: Path, max_bytes: int) -> int:
    written = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(413, "File exceeds the upload size limit")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return written


@app.post("/api/analyze")
def analyze(upload: UploadFile = File(...)):
    filename = safe_name(upload.filename or "document")
    destination = unique_destination(settings.inbox, filename)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        _save_upload_with_limit(upload, destination, max_bytes)
    except HTTPException as exc:
        if exc.status_code == 413:
            exc.detail = f"File exceeds {settings.max_upload_mb} MB limit"
        raise
    data = _analyze_and_index(destination)
    data["source_mode"] = "copy"
    audit(settings, "imported-copy", {"path": str(destination), "id": data["id"]})
    return data


@app.post("/api/apply")
def apply(request: ApplyRequest):
    try:
        final_category = request.category
        if request.mode == "organize" and request.smart_structure:
            preview = analyze_file(Path(request.source_path), custom_types=list_custom_types(settings))
            year = str((preview.metadata.document_date or date.today()).year)
            issuer = safe_name(preview.metadata.issuer or "Unknown")
            final_category = str(Path(request.category) / year / issuer)
        change = apply_change(settings, Path(request.source_path), final_category, request.filename, request.mode)
        delete_document_by_path(settings, request.source_path)
        indexed = _analyze_and_index(Path(change.destination), profile=request.profile)
        if request.case_name or request.action_required:
            update_document_fields(
                settings,
                indexed["id"],
                case_name=request.case_name or indexed.get("suggested_case"),
                action_required=request.action_required or indexed.get("action_required"),
                profile=request.profile,
            )
        audit(settings, change.action, change.model_dump(mode="json"))
        result = change.model_dump(mode="json")
        result["document_id"] = indexed["id"]
        return result
    except FileNotFoundError as exc:
        raise HTTPException(404, f"Source file not found: {exc}")
    except (ValueError, PermissionError, OSError, RuntimeError) as exc:
        logger.exception("file operation failed")
        raise HTTPException(400, str(exc))


@app.post("/api/open-folder")
def open_folder(payload: dict = Body(...)):
    raw = payload.get("path")
    if not raw:
        raise HTTPException(400, "Path is required")
    path = Path(raw).resolve()
    folder = path if path.is_dir() else path.parent
    if not folder.exists():
        raise HTTPException(404, "Folder not found")
    try:
        if os.name == "nt":
            if path.exists() and path.is_file():
                subprocess.Popen(["explorer.exe", f'/select,"{path}"'])
            else:
                subprocess.Popen(["explorer.exe", str(folder)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(path)] if path.is_file() else ["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:
        raise HTTPException(500, f"Could not open file manager: {exc}")
    return {"opened": str(folder)}


@app.post("/api/undo/{change_id}")
def undo(change_id: str):
    try:
        restored = undo_change(settings, change_id)
        _analyze_and_index(restored)
        audit(settings, "undo", {"id": change_id, "restored_to": str(restored)})
    except FileNotFoundError:
        raise HTTPException(404, "Change not found or file no longer exists")
    return {"id": change_id, "restored_to": str(restored)}


@app.get("/api/changes")
def changes():
    return [change.model_dump(mode="json") for change in list_changes(settings)]


@app.get("/api/dashboard")
def dashboard():
    docs = list_documents(settings, limit=5000)
    today = date.today()
    deadlines = []
    actions = 0
    unhealthy = 0
    for d in docs:
        md = d.get("metadata") or {}
        deadline = md.get("deadline") or md.get("warranty_until")
        if deadline:
            try:
                day = date.fromisoformat(str(deadline))
                delta = (day - today).days
                if delta >= -7:
                    deadlines.append({"id": d["id"], "name": d["source_name"], "date": day.isoformat(), "days": delta, "action": d.get("action_required")})
            except ValueError:
                pass
        if d.get("action_required"):
            actions += 1
        if int(d.get("health_score") or 100) < 70:
            unhealthy += 1
    deadlines.sort(key=lambda x: x["date"])
    duplicates = duplicate_groups(settings)
    return {
        "documents": len(docs),
        "deadlines": deadlines[:40],
        "deadline_count": len(deadlines),
        "actions": actions,
        "duplicate_groups": len(duplicates),
        "unhealthy": unhealthy,
        "profiles": sorted(set(d.get("profile") or "Home" for d in docs)),
        "cases": len(set(d.get("case_name") for d in docs if d.get("case_name"))),
    }


@app.get("/api/documents")
def documents(limit: int = 500):
    return list_documents(settings, limit=min(max(limit, 1), 5000))


@app.patch("/api/documents/{doc_id}")
def patch_document(doc_id: int, payload: dict = Body(...)):
    update_document_fields(settings, doc_id, **payload)
    audit(settings, "document-update", {"id": doc_id, **payload})
    return get_document(settings, doc_id)


@app.get("/api/search")
def search(q: str, limit: int = 50):
    docs = list_documents(settings, limit=5000)
    ranked = semantic_rank(q, docs, limit=min(max(limit, 1), 100))
    return [
        {**r.document, "meaning_score": round(r.score, 4), "vector_score": round(r.vector_score, 4), "lexical_score": round(r.lexical_score, 4)}
        for r in ranked
    ]


@app.post("/api/qa")
def qa(payload: dict = Body(...)):
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Question is required")
    return answer_local(question, list_documents(settings, limit=5000))


@app.get("/api/review")
def review_queue():
    docs = list_documents(settings, limit=5000)
    return build_review_queue(docs, duplicate_groups(settings))


@app.get("/api/duplicates")
def duplicates():
    return duplicate_groups(settings)


@app.get("/api/cases")
def cases():
    docs = list_documents(settings, limit=5000)
    groups: dict[str, list[dict]] = {}
    for d in docs:
        case = d.get("case_name")
        if case:
            groups.setdefault(case, []).append(d)
    out = []
    for name, items in groups.items():
        items.sort(key=lambda d: ((d.get("metadata") or {}).get("document_date") or d.get("updated_at") or ""))
        out.append({"name": name, "documents": items, "timeline": [
            {
                "id": d["id"], "name": d["source_name"],
                "date": (d.get("metadata") or {}).get("document_date") or d.get("updated_at"),
                "deadline": (d.get("metadata") or {}).get("deadline"),
                "action": d.get("action_required"),
            } for d in items
        ]})
    return sorted(out, key=lambda x: x["name"].lower())


@app.get("/api/audit")
def audit_log(limit: int = 200):
    return list_audit(settings, limit=min(limit, 1000))


@app.post("/api/batch/select-folder")
def batch_select_folder(payload: dict = Body(default={})):
    try:
        selected = _pick_folder_windows() if os.name == "nt" else _pick_folder_fallback()
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not selected:
        return {"cancelled": True}
    return _index_folder(Path(selected), int(payload.get("limit") or 100), str(payload.get("profile") or "Home"))


def _index_folder(folder: Path, limit: int = 100, profile: str = "Home") -> dict:
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".txt", ".md", ".csv", ".json", ".eml"}
    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in allowed][:max(1, min(limit, 1000))]
    results, errors = [], []
    for path in files:
        try:
            results.append(_analyze_and_index(path, profile=profile))
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})
    audit(settings, "batch-index", {"folder": str(folder), "count": len(results), "errors": len(errors)})
    return {"folder": str(folder), "indexed": len(results), "errors": errors[:50], "documents": results}


@app.post("/api/watch/select-folder")
def watch_select_folder():
    try:
        selected = _pick_folder_windows("Select a folder to watch") if os.name == "nt" else _pick_folder_fallback("Select a folder to watch")
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not selected:
        return {"cancelled": True}
    set_setting(settings, "watch_folder", selected)
    _ensure_watcher()
    audit(settings, "watch-folder", {"path": selected})
    return {"watch_folder": selected}


@app.get("/api/watch")
def watch_status():
    return {"watch_folder": get_setting(settings, "watch_folder"), "active": bool(WATCHER_THREAD and WATCHER_THREAD.is_alive())}


def _ensure_watcher() -> None:
    global WATCHER_THREAD
    if WATCHER_THREAD and WATCHER_THREAD.is_alive():
        return
    WATCHER_STOP.clear()
    WATCHER_THREAD = threading.Thread(target=_watch_loop, name="docpilot-watch", daemon=True)
    WATCHER_THREAD.start()


def _watch_loop() -> None:
    while not WATCHER_STOP.is_set():
        folder = get_setting(settings, "watch_folder")
        if folder and Path(folder).exists():
            try:
                _index_folder(Path(folder), limit=500, profile="Home")
            except Exception:
                logger.exception("watch folder scan failed")
        WATCHER_STOP.wait(30)


@app.post("/api/email/import-eml")
def import_eml():
    try:
        selected = _pick_file_windows("Select an .eml email file") if os.name == "nt" else _pick_file_fallback("Select an .eml email file")
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not selected:
        return {"cancelled": True}
    path = Path(selected)
    if path.suffix.lower() != ".eml":
        raise HTTPException(400, "Select an .eml file exported from your email client.")
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    imported = []
    for part in msg.iter_attachments():
        filename = safe_name(part.get_filename() or "attachment")
        data = part.get_payload(decode=True)
        if not data:
            continue
        dest = unique_destination(settings.inbox, filename)
        dest.write_bytes(data)
        try:
            imported.append(_analyze_and_index(dest))
        except Exception as exc:
            imported.append({"source_name": filename, "error": str(exc)})
    audit(settings, "email-eml-import", {"source": str(path), "attachments": len(imported)})
    return {"source": str(path), "subject": msg.get("subject"), "attachments": imported}


@app.post("/api/diff/select")
def diff_select():
    try:
        a = _pick_file_windows("Select the OLD document") if os.name == "nt" else _pick_file_fallback("Select the OLD document")
        if not a:
            return {"cancelled": True}
        b = _pick_file_windows("Select the NEW document") if os.name == "nt" else _pick_file_fallback("Select the NEW document")
        if not b:
            return {"cancelled": True}
        result = compare_documents(Path(a), Path(b))
        audit(settings, "document-diff", {"a": a, "b": b, "similarity": result["similarity"]})
        return {"a": a, "b": b, **result}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/redact/{doc_id}")
def redact(doc_id: int):
    doc = get_document(settings, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    source = Path(doc["path"])
    if not source.exists():
        raise HTTPException(404, "Source file no longer exists")
    destination = unique_destination(settings.redacted, f"{source.stem}-redacted{source.suffix}")
    try:
        output, found, warnings = redact_file(source, destination, doc.get("extracted_text", ""))
    except Exception as exc:
        raise HTTPException(400, str(exc))
    audit(settings, "redaction", {"source": str(source), "destination": str(output), "matches": len(found)})
    return {"path": str(output), "sensitive": found, "warnings": warnings}


@app.get("/api/rules")
def rules_list():
    return list_rules(settings)


@app.post("/api/rules")
def rules_add(payload: dict = Body(...)):
    rule_id = add_rule(settings, payload)
    audit(settings, "rule-added", {"id": rule_id, **payload})
    return {"id": rule_id}


@app.get("/api/custom-types")
def custom_types_list():
    return list_custom_types(settings)


@app.post("/api/custom-types")
def custom_types_add(payload: dict = Body(...)):
    name = str(payload.get("name") or "").strip()
    keywords = payload.get("keywords") or []
    category = str(payload.get("category") or "Documents")
    if not name or not isinstance(keywords, list):
        raise HTTPException(400, "name and keywords[] are required")
    item_id = add_custom_type(settings, name, [str(x) for x in keywords], category)
    audit(settings, "custom-type-added", {"id": item_id, "name": name})
    return {"id": item_id}


@app.get("/api/export/calendar")
def export_calendar():
    path = settings.exports / "docpilot-deadlines.ics"
    path.write_text(ics_for_documents(list_documents(settings, 5000)), encoding="utf-8")
    return FileResponse(path, filename=path.name, media_type="text/calendar")


@app.get("/api/export/notion")
def export_notion():
    path = settings.exports / "docpilot-notion.csv"
    path.write_text(notion_csv(list_documents(settings, 5000)), encoding="utf-8-sig")
    return FileResponse(path, filename=path.name, media_type="text/csv")


@app.get("/api/export/obsidian")
def export_obsidian():
    path = settings.exports / "docpilot-obsidian.zip"
    obsidian_zip(path, list_documents(settings, 5000))
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.get("/api/export/backup")
def export_backup():
    path = settings.exports / f"docpilot-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    backup_zip(path, settings.state, list_documents(settings, 5000))
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.get("/api/export/backup-full")
def export_backup_full():
    path = settings.exports / f"docpilot-full-archive-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    full_archive_backup(path, settings.state, list_documents(settings, 5000))
    audit(settings, "full-archive-backup", {"path": str(path)})
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.post("/api/open-export-folder")
def open_export_folder():
    return open_folder({"path": str(settings.exports)})



@app.post("/api/scan/clean-select")
def clean_scan_select():
    try:
        selected = _pick_file_windows("Select an image to clean") if os.name == "nt" else _pick_file_fallback("Select an image to clean")
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not selected:
        return {"cancelled": True}
    source = Path(selected)
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        raise HTTPException(400, "Scan cleanup currently accepts image files.")
    dest = unique_destination(settings.exports, f"{source.stem}-cleaned.jpg")
    try:
        output, notes, quality = save_clean_copy(source, dest)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    audit(settings, "scan-clean", {"source": str(source), "destination": str(output), "quality": quality})
    return {"path": str(output), "notes": notes, "quality": quality}


@app.get("/api/notifications/status")
def notification_status():
    configured = get_setting(settings, "background_notifications", "0") == "1"
    return {"enabled": configured, "days_ahead": int(get_setting(settings, "notification_days", "3") or 3)}


@app.post("/api/notifications/enable")
def notification_enable(payload: dict = Body(default={})):
    days = max(0, min(int(payload.get("days_ahead") or 3), 30))
    try:
        if os.name == "nt" and getattr(sys, "frozen", False):
            notifier_exe = Path(sys.executable).parent / "DocPilotNotifier.exe"
            if not notifier_exe.exists():
                raise RuntimeError("DocPilotNotifier.exe is missing from this build.")
            install_notifier_startup(str(notifier_exe))
        else:
            install_notifier_startup()
        set_setting(settings, "background_notifications", "1")
        set_setting(settings, "notification_days", str(days))
        shown = notify_once(days)
        audit(settings, "notifications-enabled", {"days_ahead": days})
        return {"enabled": True, "days_ahead": days, "test_notifications": shown}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/notifications/disable")
def notification_disable():
    try:
        remove_notifier_startup()
    finally:
        set_setting(settings, "background_notifications", "0")
    audit(settings, "notifications-disabled", {})
    return {"enabled": False}


@app.post("/api/notifications/test")
def notification_test(payload: dict = Body(default={})):
    days = max(0, min(int(payload.get("days_ahead") or 3), 30))
    return {"shown": notify_once(days)}


def _integration_status():
    return {"email": imap_status(settings), "notion": notion_status(settings), "google_calendar": google_calendar_status(settings)}


@app.get("/api/integrations/status")
def integrations_status():
    return _integration_status()


@app.post("/api/integrations/email")
def integration_email_config(payload: dict = Body(...)):
    try:
        result = configure_imap(
            settings,
            provider=str(payload.get("provider") or "gmail"),
            email_address=str(payload.get("email") or "").strip(),
            password=str(payload.get("password") or ""),
            folder=str(payload.get("folder") or "INBOX"),
        )
        if not result["email"] or not payload.get("password"):
            raise ValueError("Email address and app password are required.")
        audit(settings, "email-connector-configured", {"provider": result["provider"], "email": result["email"]})
        return result
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/email/import-imap")
def import_imap(payload: dict = Body(default={})):
    def destination(name: str) -> Path:
        return unique_destination(settings.inbox, safe_name(name))
    try:
        items = import_imap_attachments(settings, destination, unread_only=bool(payload.get("unread_only", True)), max_messages=int(payload.get("max_messages") or 20))
        imported = []
        for item in items:
            try:
                imported.append(_analyze_and_index(Path(item["path"])))
            except Exception as exc:
                imported.append({**item, "error": str(exc)})
        audit(settings, "email-imap-import", {"attachments": len(imported)})
        return {"attachments": imported}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/integrations/notion")
def integration_notion_config(payload: dict = Body(...)):
    try:
        result = configure_notion(settings, str(payload.get("token") or ""), str(payload.get("database_id") or ""))
        audit(settings, "notion-configured", {"database_id": result.get("database_id")})
        return result
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/integrations/notion/sync")
def integration_notion_sync(payload: dict = Body(default={})):
    try:
        result = sync_notion(settings, list_documents(settings, 5000), limit=int(payload.get("limit") or 100))
        audit(settings, "notion-sync", result)
        return result
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/integrations/google-calendar/select-client")
def integration_google_select_client():
    try:
        selected = _pick_file_windows("Select Google OAuth client_secret.json") if os.name == "nt" else _pick_file_fallback("Select Google OAuth client_secret.json")
        if not selected:
            return {"cancelled": True}
        result = configure_google_calendar(settings, selected)
        audit(settings, "google-calendar-configured", {"client_secret": selected})
        return result
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/integrations/google-calendar/sync")
def integration_google_sync(payload: dict = Body(default={})):
    try:
        result = sync_google_calendar(settings, list_documents(settings, 5000), calendar_id=str(payload.get("calendar_id") or "primary"))
        audit(settings, "google-calendar-sync", result)
        return result
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.on_event("startup")
def startup_event():
    if get_setting(settings, "watch_folder"):
        _ensure_watcher()
