from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
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
    SCHEMA,
    add_custom_type,
    add_rule,
    audit,
    dashboard_summary,
    delete_document_by_path,
    delete_rule,
    duplicate_display_groups,
    duplicate_group_count,
    duplicate_groups,
    review_candidate_documents,
    get_document,
    get_setting,
    init_db,
    list_audit,
    list_case_documents,
    list_custom_types,
    list_document_page,
    list_documents,
    list_documents_for_integration,
    list_integration_runs,
    list_rules,
    search_documents,
    semantic_candidate_documents,
    set_setting,
    start_integration_run,
    finish_integration_run,
    update_document_fields,
    update_document_metadata,
    update_documents_fields,
    update_rule,
    upsert_document,
)
from .db_maintenance import create_database_checkpoint, database_health, list_recovery_points, restore_database_from_point
from .diffing import compare_documents
from .exporters import backup_zip, full_archive_backup, ics_for_documents, notion_csv, obsidian_zip
from .semantic import semantic_rank
from .qa import answer_local
from .review import build_review_queue
from .preprocess import save_clean_copy
from .portable_config import FORMAT_VERSION as PORTABLE_CONFIG_FORMAT_VERSION, export_portable_config, import_portable_config, preview_portable_config
from .integrations import (
    configure_google_calendar, configure_imap, configure_notion, import_imap_attachments,
)
from .integration_registry import get_integration_adapter, integration_catalog
from .lifepilot import attention_signature, build_case_summary, build_lifepilot_view, build_proof_pack, case_summary_markdown, handled_entry_done_at, handled_entry_matches, lifepilot_queue, proof_pack_preview
from .notifier import install_startup as install_notifier_startup, remove_startup as remove_notifier_startup, notify_once
from .models import ApplyRequest, LifePilotCorrectionRequest
from .redaction import redact_file
from .rules import apply_rules
from .storage import apply_change, get_change, list_changes, safe_name, undo_change, unique_destination
from .update_safety import ensure_version_recovery

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates" if (BASE_DIR / "templates").exists() else BASE_DIR
PACKAGED_STATIC_DIR = BASE_DIR / "static"
STATIC_DIR = PACKAGED_STATIC_DIR if PACKAGED_STATIC_DIR.exists() else BASE_DIR
DEMO_DIR = BASE_DIR / "demo" if (BASE_DIR / "demo").exists() else BASE_DIR

settings = get_settings()
init_db(settings)

LOG_PATH = settings.state / "docpilot.log"
logger = logging.getLogger("docpilot")
logger.setLevel(logging.INFO)
UPGRADE_RECOVERY_STATUS: dict[str, Any] = {
    "status": "not-run",
    "previous_version": None,
    "current_version": __version__,
    "checkpoint": None,
}
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global UPGRADE_RECOVERY_STATUS
    try:
        UPGRADE_RECOVERY_STATUS = ensure_version_recovery(settings, __version__)
        if UPGRADE_RECOVERY_STATUS.get("status") == "checkpointed":
            audit(
                settings,
                "upgrade-recovery-checkpoint",
                {
                    "previous_version": UPGRADE_RECOVERY_STATUS.get("previous_version"),
                    "current_version": UPGRADE_RECOVERY_STATUS.get("current_version"),
                    "checkpoint": UPGRADE_RECOVERY_STATUS.get("checkpoint"),
                },
            )
    except Exception as exc:
        logger.exception("upgrade recovery checkpoint failed")
        try:
            previous_version = get_setting(settings, "last_started_version")
        except Exception:
            previous_version = None
        UPGRADE_RECOVERY_STATUS = {
            "status": "error",
            "previous_version": previous_version,
            "current_version": __version__,
            "checkpoint": None,
            "message": str(exc),
        }

    if get_setting(settings, "watch_folder"):
        _ensure_watcher()
    try:
        yield
    finally:
        WATCHER_STOP.set()


app = FastAPI(title="DocPilot", version=__version__, lifespan=lifespan)

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


@app.get("/lifepilot")
def lifepilot_about():
    return FileResponse(
        TEMPLATE_DIR / "lifepilot.html",
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


def _diagnostic_assessment(report: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    recommendations: list[str] = []

    database_status = str(report.get("database") or "unknown")
    integrity = str(report.get("database_integrity") or "unknown")
    schema = int(report.get("schema_version") or 0)
    supported = int(report.get("supported_schema_version") or 0)
    free_space = float(report.get("free_space_gb") or 0)

    if database_status == "missing":
        checks.append({"code": "database", "status": "info", "message": "Database has not been created yet."})
    elif integrity != "ok":
        checks.append({"code": "database", "status": "error", "message": f"Database integrity: {integrity}."})
        recommendations.append("Open Settings → Recovery checkpoints and restore a verified recovery point if the database cannot be used.")
    else:
        checks.append({"code": "database", "status": "ok", "message": "Database integrity is OK."})

    if schema > supported:
        checks.append({"code": "schema", "status": "error", "message": f"Database schema v{schema} is newer than supported v{supported}."})
        recommendations.append("Update DocPilot before making further database changes.")
    elif database_status != "missing" and schema < supported:
        checks.append({"code": "schema", "status": "warning", "message": f"Database schema v{schema} has not reached supported v{supported}."})
        recommendations.append("Restart DocPilot so the guarded database migration can complete.")
    else:
        checks.append({"code": "schema", "status": "ok", "message": f"Schema compatibility is OK (v{schema} / v{supported})."})

    upgrade_recovery = report.get("upgrade_recovery") or {}
    upgrade_status = str(upgrade_recovery.get("status") or "not-run")
    if upgrade_status == "error":
        checks.append({
            "code": "upgrade-recovery",
            "status": "warning",
            "message": "DocPilot could not create the automatic recovery checkpoint for this version change.",
        })
        recommendations.append(
            "Create a verified Recovery checkpoint manually before large imports, maintenance or another update."
        )
    elif upgrade_status == "checkpointed":
        checks.append({
            "code": "upgrade-recovery",
            "status": "ok",
            "message": "A verified recovery checkpoint was created for the version change.",
        })
    elif upgrade_status in {"initialized", "current"}:
        checks.append({
            "code": "upgrade-recovery",
            "status": "ok",
            "message": "Version recovery state is current.",
        })

    if free_space < 0.25:
        checks.append({"code": "disk", "status": "error", "message": f"Only {free_space:.2f} GB of free disk space remains."})
        recommendations.append("Free disk space before importing, OCRing, backing up or updating documents.")
    elif free_space < 1.0:
        checks.append({"code": "disk", "status": "warning", "message": f"Free disk space is low: {free_space:.2f} GB."})
        recommendations.append("Free some disk space before creating large backups or importing many documents.")
    else:
        checks.append({"code": "disk", "status": "ok", "message": f"Free disk space: {free_space:.2f} GB."})

    severity = {"ok": 0, "info": 0, "warning": 1, "error": 2}
    max_level = max((severity.get(item["status"], 0) for item in checks), default=0)
    overall = "error" if max_level >= 2 else "warning" if max_level == 1 else "ok"
    if not recommendations:
        recommendations.append("No immediate maintenance action is required.")

    return {"status": overall, "checks": checks, "recommendations": recommendations}


@app.get("/api/diagnostics")
def diagnostics():
    usage = shutil.disk_usage(settings.root)
    db_path = settings.state / "docpilot.sqlite3"
    summary = dashboard_summary(settings)
    db_health = database_health(db_path)

    recovery_points = list_recovery_points(settings.state)
    usable_recovery = [
        point
        for point in recovery_points
        if str(point.get("integrity") or "").lower() == "ok"
        and int(point.get("schema_version") or 0) <= int(db_health["supported_schema_version"])
    ]
    latest_recovery = usable_recovery[0] if usable_recovery else None

    if str(db_health["integrity"]).lower() != "ok":
        recovery_status = "database-problem"
        recovery_message = "Database integrity needs attention. Use a verified recovery point only if the current database cannot be used safely."
    elif not usable_recovery:
        recovery_status = "checkpoint-recommended"
        recovery_message = "Database is healthy, but no verified recovery point is available. Create a checkpoint before major maintenance, bulk changes or an update."
    else:
        recovery_status = "ready"
        recovery_message = "Database is healthy and at least one verified recovery point is available."
    safe_report = {
        "version": __version__,
        "packaged": bool(getattr(sys, "frozen", False)),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "documents": summary["documents"],
        "database": db_health["status"],
        "database_integrity": db_health["integrity"],
        "schema_version": db_health["schema_version"],
        "supported_schema_version": db_health["supported_schema_version"],
        "migration_backups": db_health["migration_backups"],
        "recovery_points": len(recovery_points),
        "verified_recovery_points": len(usable_recovery),
        "recovery_status": recovery_status,
        "recovery_message": recovery_message,
        "latest_recovery_point": latest_recovery["modified_at"] if latest_recovery else None,
        "free_space_gb": round(usage.free / (1024 ** 3), 2),
        "max_upload_mb": settings.max_upload_mb,
        "portable_config_format": PORTABLE_CONFIG_FORMAT_VERSION,
        "upgrade_recovery": {
            "status": UPGRADE_RECOVERY_STATUS.get("status"),
            "previous_version": UPGRADE_RECOVERY_STATUS.get("previous_version"),
            "current_version": UPGRADE_RECOVERY_STATUS.get("current_version"),
            "checkpoint": UPGRADE_RECOVERY_STATUS.get("checkpoint"),
        },
    }
    assessment = _diagnostic_assessment(safe_report)
    return {
        **safe_report,
        "data_root": str(settings.root),
        "database_path": str(db_path),
        "log_path": str(LOG_PATH),
        "safe_report": {**safe_report, "assessment": assessment},
        "assessment": assessment,
    }


@app.get("/api/diagnostics/report")
def diagnostics_report():
    data = diagnostics()
    report = data["safe_report"]
    assessment = report["assessment"]
    lines = [
        "DocPilot safe diagnostic report",
        f"Version: {report['version']}",
        f"Mode: {'packaged' if report['packaged'] else 'source'}",
        f"Platform: {report['platform']}",
        f"Documents: {report['documents']}",
        f"Database: {report['database']} / integrity {report['database_integrity']}",
        f"Schema: v{report['schema_version']} / supported v{report['supported_schema_version']}",
        f"Migration backups: {report['migration_backups']}",
        f"Recovery readiness: {report['recovery_status']}",
        f"Verified recovery points: {report['verified_recovery_points']}",
        f"Latest recovery point: {report['latest_recovery_point'] or 'none'}",
        f"Upgrade recovery: {report['upgrade_recovery']['status']}",
        f"Upgrade checkpoint: {report['upgrade_recovery'].get('checkpoint') or 'none'}",
        f"Free space: {report['free_space_gb']} GB",
        f"Overall status: {assessment['status']}",
        "",
        "Checks:",
        *[f"- [{item['status']}] {item['message']}" for item in assessment["checks"]],
        "",
        "Recommended next steps:",
        *[f"- {item}" for item in assessment["recommendations"]],
        "",
        "This report intentionally excludes document contents, local file paths and credentials.",
    ]
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": 'attachment; filename="docpilot-safe-diagnostics.txt"'},
    )


@app.get("/api/recovery")
def recovery_points():
    return list_recovery_points(settings.state)


@app.post("/api/recovery/checkpoint")
def recovery_checkpoint():
    db_path = settings.state / "docpilot.sqlite3"
    try:
        checkpoint = create_database_checkpoint(db_path)
    except FileNotFoundError:
        raise HTTPException(404, "Database not found")
    except (RuntimeError, sqlite3.DatabaseError) as exc:
        raise HTTPException(409, str(exc))
    audit(settings, "recovery-checkpoint", {"name": checkpoint["name"]})
    return checkpoint


@app.post("/api/recovery/restore")
def recovery_restore(payload: dict = Body(...)):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Recovery point name is required")
    if payload.get("confirm") != "RESTORE":
        raise HTTPException(400, "Type RESTORE to confirm database recovery")

    db_path = settings.state / "docpilot.sqlite3"
    try:
        result = restore_database_from_point(db_path, name, SCHEMA)
    except FileNotFoundError:
        raise HTTPException(404, "Recovery point not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except (RuntimeError, sqlite3.DatabaseError, OSError) as exc:
        raise HTTPException(409, str(exc))

    audit(
        settings,
        "recovery-restore",
        {
            "restored_from": result["restored_from"]["name"],
            "pre_restore_backup": (result.get("pre_restore_backup") or {}).get("name"),
        },
    )
    return result


def _ocr_runtime_status() -> dict[str, Any]:
    try:
        import pytesseract
        from .extract import _configure_tesseract

        _configure_tesseract(pytesseract)
        version = str(pytesseract.get_tesseract_version()).splitlines()[0]
        return {"ready": True, "version": version}
    except Exception as exc:
        logger.warning("OCR readiness check failed: %s", exc)
        return {"ready": False, "version": None}


def _setup_status_payload() -> dict[str, Any]:
    usage = shutil.disk_usage(settings.root)
    try:
        demo_ready = _demo_source_path().exists()
    except FileNotFoundError:
        demo_ready = False
    return {
        "complete": get_setting(settings, "onboarding_complete", "0") == "1",
        "has_documents": bool(list_documents(settings, limit=1)),
        "ocr": _ocr_runtime_status(),
        "demo_ready": demo_ready,
        "packaged": bool(getattr(sys, "frozen", False)),
        "data_root": str(settings.root),
        "free_space_gb": round(usage.free / (1024 ** 3), 2),
        "recommended_free_space_gb": 2,
    }


@app.get("/api/setup/status")
def setup_status():
    return _setup_status_payload()


@app.post("/api/setup")
def update_setup(payload: dict = Body(default={})):
    complete = bool(payload.get("complete", True))
    set_setting(settings, "onboarding_complete", "1" if complete else "0")
    audit(settings, "setup-state", {"complete": complete})
    return _setup_status_payload()


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
    data["matched_rules"] = ruled.get("matched_rules", [])
    stored = get_document(settings, doc_id)
    if stored:
        data["lifepilot"] = build_lifepilot_view(stored)
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


def _lifepilot_done_map() -> dict[str, Any]:
    raw = get_setting(settings, "lifepilot.done", "{}") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@app.get("/api/lifepilot/queue")
def lifepilot_action_queue(limit: int = 200, include_done: bool = False):
    documents = list_documents(settings, limit=min(max(int(limit), 1), 5000))
    done = _lifepilot_done_map()
    if include_done:
        items = lifepilot_queue(documents, limit=limit)
        by_id = {int(doc.get("id")): doc for doc in documents if doc.get("id") is not None}
        for item in items:
            document = by_id.get(int(item.get("id") or 0))
            entry = done.get(str(item.get("id")))
            item["done"] = bool(document and handled_entry_matches(entry, document))
            item["done_at"] = handled_entry_done_at(entry) if item["done"] else None
        return items
    active = [
        document for document in documents
        if not handled_entry_matches(done.get(str(document.get("id"))), document)
    ]
    return lifepilot_queue(active, limit=limit)


@app.get("/api/lifepilot/case-summary")
def lifepilot_case_summary(case_name: str):
    name = str(case_name or "").strip()
    if not name:
        raise HTTPException(400, "case_name is required")
    documents = list_case_documents(settings, limit=5000)
    summary = build_case_summary(name, documents)
    if not summary["document_count"]:
        raise HTTPException(404, "Case not found")
    return summary


@app.get("/api/lifepilot/case-summary/export")
def lifepilot_case_summary_export(case_name: str):
    name = str(case_name or "").strip()
    if not name:
        raise HTTPException(400, "case_name is required")
    documents = list_case_documents(settings, limit=5000)
    summary = build_case_summary(name, documents)
    if not summary["document_count"]:
        raise HTTPException(404, "Case not found")
    content = case_summary_markdown(summary)
    filename = f"LifePilot-Case-{safe_name(name)}.md"
    audit(settings, "lifepilot-case-summary-exported", {"case_name": name, "documents": summary["document_count"]})
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/lifepilot/{doc_id}")
def lifepilot_view(doc_id: int):
    document = get_document(settings, doc_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return build_lifepilot_view(document)


@app.patch("/api/lifepilot/{doc_id}/fields")
def lifepilot_correct_fields(doc_id: int, request: LifePilotCorrectionRequest):
    before = get_document(settings, doc_id)
    if not before:
        raise HTTPException(404, "Document not found")

    payload = request.model_dump(exclude_unset=True)
    metadata_keys = {"document_type", "issuer", "amount", "currency", "document_date", "deadline", "warranty_until"}
    metadata_updates = {key: payload[key] for key in metadata_keys if key in payload}
    top_updates = {key: payload[key] for key in ("case_name", "action_required") if key in payload}

    if "document_type" in metadata_updates:
        value = str(metadata_updates["document_type"] or "").strip()
        metadata_updates["document_type"] = value or "document"
    if "issuer" in metadata_updates:
        value = metadata_updates["issuer"]
        metadata_updates["issuer"] = str(value).strip() if value is not None else None
    if "currency" in metadata_updates:
        value = metadata_updates["currency"]
        normalized = str(value or "").strip().upper()
        if normalized and (len(normalized) != 3 or not normalized.isalpha()):
            raise HTTPException(400, "Currency must be a 3-letter code, for example PLN or EUR")
        metadata_updates["currency"] = normalized or None

    if metadata_updates:
        metadata_updates["manual_verified"] = True
        metadata_updates["manual_verified_at"] = datetime.now(timezone.utc).isoformat()
        update_document_metadata(settings, doc_id, **metadata_updates)
    if top_updates:
        update_document_fields(settings, doc_id, **top_updates)

    after = get_document(settings, doc_id)
    audit(
        settings,
        "lifepilot-fields-corrected",
        {
            "document_id": doc_id,
            "fields": sorted(payload.keys()),
            "case_before": before.get("case_name"),
            "case_after": after.get("case_name") if after else None,
        },
    )
    if not after:
        raise HTTPException(404, "Document not found")
    return {**after, "lifepilot": build_lifepilot_view(after)}


@app.get("/api/lifepilot/{doc_id}/proofpack-preview")
def lifepilot_proofpack_preview(doc_id: int):
    document = get_document(settings, doc_id)
    if not document:
        raise HTTPException(404, "Document not found")
    case_name = str(document.get("case_name") or "").strip()
    timeline = [document]
    if case_name:
        timeline = [item for item in list_case_documents(settings, limit=5000) if item.get("case_name") == case_name]
    return proof_pack_preview(document, timeline_documents=timeline)


@app.post("/api/lifepilot/{doc_id}/done")
def lifepilot_mark_done(doc_id: int):
    document = get_document(settings, doc_id)
    if not document:
        raise HTTPException(404, "Document not found")
    done = _lifepilot_done_map()
    done_at = datetime.now(timezone.utc).isoformat()
    done[str(doc_id)] = {
        "version": 2,
        "signature": attention_signature(document),
        "done_at": done_at,
    }
    set_setting(settings, "lifepilot.done", json.dumps(done, ensure_ascii=False, sort_keys=True))
    audit(settings, "lifepilot-mark-done", {"document_id": doc_id, "done_at": done_at})
    return {"document_id": doc_id, "done": True, "done_at": done_at}


@app.post("/api/lifepilot/{doc_id}/reopen")
def lifepilot_reopen(doc_id: int):
    done = _lifepilot_done_map()
    done.pop(str(doc_id), None)
    set_setting(settings, "lifepilot.done", json.dumps(done, ensure_ascii=False, sort_keys=True))
    audit(settings, "lifepilot-reopen", {"document_id": doc_id})
    return {"document_id": doc_id, "done": False}


@app.get("/api/lifepilot/{doc_id}/proofpack")
def lifepilot_proofpack(doc_id: int):
    document = get_document(settings, doc_id)
    if not document:
        raise HTTPException(404, "Document not found")
    case_name = str(document.get("case_name") or "").strip()
    timeline = [document]
    if case_name:
        timeline = [item for item in list_case_documents(settings, limit=5000) if item.get("case_name") == case_name]
    filename = f"LifePilot-ProofPack-{doc_id}.zip"
    destination = settings.exports / filename
    try:
        build_proof_pack(destination, document, timeline_documents=timeline)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except (OSError, ValueError, RuntimeError) as exc:
        logger.exception("proof pack export failed")
        raise HTTPException(400, f"Could not create ProofPack: {exc}")
    audit(settings, "lifepilot-proofpack-exported", {"document_id": doc_id, "case_name": case_name or None})
    return FileResponse(destination, media_type="application/zip", filename=filename)


@app.get("/api/lifepilot/{doc_id}/calendar")
def lifepilot_calendar(doc_id: int):
    document = get_document(settings, doc_id)
    if not document:
        raise HTTPException(404, "Document not found")
    deadline = (document.get("metadata") or {}).get("deadline") or (document.get("metadata") or {}).get("warranty_until")
    if not deadline:
        raise HTTPException(400, "Document has no detected deadline")
    content = ics_for_documents([document])
    return PlainTextResponse(
        content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="LifePilot-{doc_id}-deadline.ics"'},
    )


@app.post("/api/apply")
def apply(request: ApplyRequest):
    try:
        final_category = request.category
        if request.mode == "organize" and request.smart_structure:
            preview = analyze_file(Path(request.source_path), custom_types=list_custom_types(settings))
            year = str((preview.metadata.document_date or date.today()).year)
            issuer = safe_name(preview.metadata.issuer or "Unknown")
            final_category = str(Path(request.category) / year / issuer)
        change = apply_change(
            settings,
            Path(request.source_path),
            final_category,
            request.filename,
            request.mode,
            profile=request.profile,
        )
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
        if request.metadata_overrides:
            allowed_override_keys = {
                "document_type", "issuer", "amount", "currency",
                "document_date", "deadline", "warranty_until",
            }
            overrides = {
                key: value for key, value in request.metadata_overrides.items()
                if key in allowed_override_keys
            }
            if overrides:
                overrides["manual_verified"] = True
                overrides["manual_verified_at"] = datetime.now(timezone.utc).isoformat()
                update_document_metadata(settings, indexed["id"], **overrides)
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
        change = get_change(settings, change_id)
        restored = undo_change(settings, change_id)
        delete_document_by_path(settings, change.destination)
        indexed = _analyze_and_index(restored)
        audit(settings, "undo", {"id": change_id, "restored_to": str(restored)})
    except FileNotFoundError:
        raise HTTPException(404, "Change not found or file no longer exists")
    return {"id": change_id, "restored_to": str(restored), "document_id": indexed["id"]}


@app.get("/api/changes")
def changes():
    return [change.model_dump(mode="json") for change in list_changes(settings)]


@app.get("/api/dashboard")
def dashboard():
    summary = dashboard_summary(settings)
    summary["duplicate_groups"] = duplicate_group_count(settings)
    return summary


@app.get("/api/documents")
def documents(limit: int = 500):
    return list_documents(settings, limit=min(max(limit, 1), 5000))


@app.get("/api/documents/page")
def documents_page(
    limit: int = 100,
    offset: int = 0,
    q: str = "",
    profile: str = "",
    case_name: str = "",
):
    page_limit = min(max(limit, 20), 250)
    page_offset = max(offset, 0)
    items, total = list_document_page(
        settings,
        limit=page_limit,
        offset=page_offset,
        query=q,
        profile=profile,
        case_name=case_name,
    )
    return {
        "items": items,
        "total": total,
        "limit": page_limit,
        "offset": page_offset,
        "has_more": page_offset + len(items) < total,
    }


@app.patch("/api/documents/{doc_id}")
def patch_document(doc_id: int, payload: dict = Body(...)):
    update_document_fields(settings, doc_id, **payload)
    audit(settings, "document-update", {"id": doc_id, **payload})
    return get_document(settings, doc_id)


@app.post("/api/documents/batch-update")
def batch_update_documents(payload: dict = Body(...)):
    raw_ids = payload.get("ids") or []
    if not isinstance(raw_ids, list):
        raise HTTPException(400, "ids must be a list")

    try:
        ids = sorted({int(value) for value in raw_ids if int(value) > 0})
    except (TypeError, ValueError):
        raise HTTPException(400, "ids must contain positive integers")

    if not ids:
        raise HTTPException(400, "Choose at least one document")
    if len(ids) > 500:
        raise HTTPException(400, "Bulk update is limited to 500 documents at a time")

    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        raise HTTPException(400, "fields must be an object")
    allowed = {"category", "profile", "case_name", "action_required"}
    actual = {key: value for key, value in fields.items() if key in allowed}
    if not actual:
        raise HTTPException(400, "Choose at least one field to update")

    updated = update_documents_fields(settings, ids, **actual)
    audit(settings, "documents-batch-update", {"ids": ids, "fields": actual, "updated": updated})
    return {"requested": len(ids), "updated": updated, "ids": ids}


@app.get("/api/search")
def search(q: str, limit: int = 50):
    docs = semantic_candidate_documents(settings, q, limit=750)
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
    docs = semantic_candidate_documents(settings, question, limit=750)
    return answer_local(question, docs)


@app.get("/api/review")
def review_queue():
    docs, duplicate_candidates = review_candidate_documents(settings, limit=1500)
    return build_review_queue(docs, duplicate_candidates)


@app.get("/api/duplicates")
def duplicates():
    return duplicate_display_groups(settings)


@app.post("/api/duplicates/compare")
def compare_duplicate_documents(payload: dict = Body(...)):
    try:
        left_id = int(payload.get("left_id"))
        right_id = int(payload.get("right_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Two document IDs are required")
    if left_id == right_id:
        raise HTTPException(400, "Choose two different documents")

    left = get_document(settings, left_id)
    right = get_document(settings, right_id)
    if not left or not right:
        raise HTTPException(404, "One of the indexed documents no longer exists")

    left_path = Path(left["path"])
    right_path = Path(right["path"])
    if not left_path.is_file() or not right_path.is_file():
        raise HTTPException(404, "One of the source files is no longer available")

    exact_hash_match = bool(left.get("sha256")) and left.get("sha256") == right.get("sha256")
    result = (
        {"similarity": 1.0, "added_lines": 0, "removed_lines": 0, "diff": "", "warnings": []}
        if exact_hash_match
        else compare_documents(left_path, right_path)
    )
    return {
        **result,
        "exact_hash_match": exact_hash_match,
        "left": {"id": left_id, "name": left["source_name"], "path": str(left_path)},
        "right": {"id": right_id, "name": right["source_name"], "path": str(right_path)},
    }


@app.get("/api/cases")
def cases():
    docs = list_case_documents(settings, limit=5000)
    groups: dict[str, list[dict]] = {}
    for d in docs:
        case = d.get("case_name")
        if case:
            groups.setdefault(case, []).append(d)

    out = []
    for name, items in groups.items():
        items.sort(key=lambda d: ((d.get("metadata") or {}).get("document_date") or d.get("updated_at") or ""))
        deadlines = sorted(
            value
            for d in items
            if (value := ((d.get("metadata") or {}).get("deadline") or (d.get("metadata") or {}).get("warranty_until")))
        )
        today_iso = date.today().isoformat()
        upcoming_deadlines = [value for value in deadlines if value >= today_iso]
        overdue_deadlines = [value for value in deadlines if value < today_iso]
        out.append({
            "name": name,
            "document_count": len(items),
            "open_actions": sum(1 for d in items if d.get("action_required")),
            "next_deadline": upcoming_deadlines[0] if upcoming_deadlines else None,
            "overdue_deadlines": len(overdue_deadlines),
            "profiles": sorted({d.get("profile") or "Home" for d in items}),
            "documents": items,
            "timeline": [
                {
                    "id": d["id"],
                    "name": d["source_name"],
                    "path": d["path"],
                    "date": (d.get("metadata") or {}).get("document_date") or d.get("updated_at"),
                    "deadline": (d.get("metadata") or {}).get("deadline") or (d.get("metadata") or {}).get("warranty_until"),
                    "action": d.get("action_required"),
                    "category": d.get("category"),
                    "profile": d.get("profile") or "Home",
                    "document_type": (d.get("metadata") or {}).get("document_type"),
                }
                for d in items
            ],
        })
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


@app.patch("/api/rules/{rule_id}")
def rules_update(rule_id: int, payload: dict = Body(...)):
    if not update_rule(settings, rule_id, payload):
        raise HTTPException(404, "Rule not found")
    audit(settings, "rule-updated", {"id": rule_id, **payload})
    return next(rule for rule in list_rules(settings) if int(rule["id"]) == rule_id)


@app.delete("/api/rules/{rule_id}")
def rules_delete(rule_id: int):
    if not delete_rule(settings, rule_id):
        raise HTTPException(404, "Rule not found")
    audit(settings, "rule-deleted", {"id": rule_id})
    return {"deleted": rule_id}


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


@app.get("/api/export/config")
def export_config():
    path = settings.exports / f"docpilot-config-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    payload = export_portable_config(settings)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    audit(settings, "portable-config-export", {"path": str(path), "format_version": payload["format_version"]})
    return FileResponse(path, filename=path.name, media_type="application/json")


@app.post("/api/config/preview")
def config_preview(payload: dict = Body(...)):
    try:
        return preview_portable_config(settings, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/config/import")
def config_import(payload: dict = Body(...)):
    try:
        result = import_portable_config(settings, payload)
        audit(settings, "portable-config-import", result)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


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


def _integration_scope(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
    limit = min(max(int(raw.get("limit") or payload.get("limit") or 100), 1), 500)
    return {
        "profile": str(raw.get("profile") or "").strip(),
        "case_name": str(raw.get("case_name") or "").strip(),
        "action_required": str(raw.get("action_required") or "").strip(),
        "category": str(raw.get("category") or "").strip(),
        "limit": limit,
    }


def _integration_documents(payload: dict[str, Any], *, provider: str) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    adapter = get_integration_adapter(provider)
    if not adapter or not adapter.supports_document_sync:
        raise HTTPException(400, f"Integration does not support document sync: {provider}")
    scope = _integration_scope(payload)
    documents, matched_total = list_documents_for_integration(
        settings,
        limit=scope["limit"],
        profile=scope["profile"],
        case_name=scope["case_name"],
        action_required=scope["action_required"],
        category=scope["category"],
    )
    return adapter.eligible_documents(documents), scope, matched_total


def _integration_status():
    return {item["key"]: item["status"] for item in integration_catalog(settings)}


@app.get("/api/integrations/status")
def integrations_status():
    return _integration_status()


@app.get("/api/integrations/catalog")
def integrations_catalog():
    return integration_catalog(settings)


@app.post("/api/integrations/preview")
def integrations_preview(payload: dict = Body(default={})):
    provider = str(payload.get("provider") or "notion").strip()
    documents, scope, matched_total = _integration_documents(payload, provider=provider)
    return {
        "provider": provider,
        "scope": scope,
        "matched_total": matched_total,
        "eligible": len(documents),
        "sample": [
            {"id": d["id"], "name": d["source_name"], "profile": d.get("profile"), "case_name": d.get("case_name")}
            for d in documents[:10]
        ],
    }


@app.get("/api/integrations/history")
def integrations_history(provider: str = "", limit: int = 30):
    return list_integration_runs(settings, provider=provider, limit=limit)


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
    max_messages = max(1, min(int(payload.get("max_messages") or 20), 100))
    scope = {"unread_only": bool(payload.get("unread_only", True)), "max_messages": max_messages}
    run_id = start_integration_run(settings, "email", "import-attachments", scope)

    def destination(name: str) -> Path:
        return unique_destination(settings.inbox, safe_name(name))

    try:
        items = import_imap_attachments(
            settings,
            destination,
            unread_only=scope["unread_only"],
            max_messages=max_messages,
        )
        imported = []
        errors: list[str] = []
        for item in items:
            try:
                imported.append(_analyze_and_index(Path(item["path"])))
            except Exception as exc:
                message = f"{item.get('name') or 'attachment'}: {exc}"
                errors.append(message)
                imported.append({**item, "error": str(exc)})
        finish_integration_run(
            settings,
            run_id,
            status="partial" if errors else "success",
            attempted=len(items),
            succeeded=len(items) - len(errors),
            failed=len(errors),
            errors=errors,
        )
        audit(settings, "email-imap-import", {"attachments": len(imported), "errors": len(errors), "run_id": run_id})
        return {"attachments": imported, "run_id": run_id, "errors": errors}
    except Exception as exc:
        finish_integration_run(settings, run_id, status="failed", failed=1, errors=[str(exc)])
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
    documents, scope, matched_total = _integration_documents(payload, provider="notion")
    run_id = start_integration_run(settings, "notion", "sync", scope)
    try:
        adapter = get_integration_adapter("notion")
        if not adapter:
            raise RuntimeError("Notion adapter is not registered.")
        result = adapter.sync_documents(settings, documents, {"limit": len(documents) or 1})
        errors = list(result.get("errors") or [])
        synced = int(result.get("synced") or 0)
        skipped = int(result.get("skipped") or 0)
        finish_integration_run(
            settings,
            run_id,
            status="partial" if errors else "success",
            attempted=len(documents),
            succeeded=synced,
            skipped=skipped,
            failed=len(errors),
            errors=errors,
        )
        response = {**result, "run_id": run_id, "scope": scope, "matched_total": matched_total, "attempted": len(documents)}
        audit(settings, "notion-sync", response)
        return response
    except Exception as exc:
        finish_integration_run(settings, run_id, status="failed", attempted=len(documents), failed=len(documents) or 1, errors=[str(exc)])
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
    documents, scope, matched_total = _integration_documents(payload, provider="google_calendar")
    calendar_id = str(payload.get("calendar_id") or "primary")
    run_scope = {**scope, "calendar_id": calendar_id}
    run_id = start_integration_run(settings, "google_calendar", "sync", run_scope)
    try:
        adapter = get_integration_adapter("google_calendar")
        if not adapter:
            raise RuntimeError("Google Calendar adapter is not registered.")
        result = adapter.sync_documents(settings, documents, {"calendar_id": calendar_id})
        errors = list(result.get("errors") or [])
        synced = int(result.get("synced") or 0)
        skipped = int(result.get("skipped") or 0)
        finish_integration_run(
            settings,
            run_id,
            status="partial" if errors else "success",
            attempted=len(documents),
            succeeded=synced,
            skipped=skipped,
            failed=len(errors),
            errors=errors,
        )
        response = {**result, "run_id": run_id, "scope": run_scope, "matched_total": matched_total, "attempted": len(documents)}
        audit(settings, "google-calendar-sync", response)
        return response
    except Exception as exc:
        finish_integration_run(settings, run_id, status="failed", attempted=len(documents), failed=len(documents) or 1, errors=[str(exc)])
        raise HTTPException(400, str(exc))
