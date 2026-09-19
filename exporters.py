from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def ics_for_documents(documents: list[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DocPilot//EN", "CALSCALE:GREGORIAN"]
    for doc in documents:
        deadline = (doc.get("metadata") or {}).get("deadline")
        if not deadline:
            continue
        uid = f"docpilot-{doc.get('id')}@local"
        summary = f"DocPilot: {doc.get('action_required') or 'deadline'} — {doc.get('source_name')}"
        lines += [
            "BEGIN:VEVENT", f"UID:{uid}", f"DTSTART;VALUE=DATE:{deadline.replace('-', '')}",
            f"SUMMARY:{_ics_escape(summary)}", f"DESCRIPTION:{_ics_escape(doc.get('path',''))}", "END:VEVENT"
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def notion_csv(documents: list[dict]) -> str:
    output = io.StringIO()
    fields = ["Name", "Path", "Type", "Issuer", "Date", "Deadline", "Amount", "Currency", "Category", "Profile", "Case", "Action", "Tags"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for d in documents:
        md = d.get("metadata") or {}
        writer.writerow({
            "Name": d.get("source_name"), "Path": d.get("path"), "Type": md.get("document_type"),
            "Issuer": md.get("issuer"), "Date": md.get("document_date"), "Deadline": md.get("deadline"),
            "Amount": md.get("amount"), "Currency": md.get("currency"), "Category": d.get("category"),
            "Profile": d.get("profile"), "Case": d.get("case_name"), "Action": d.get("action_required"),
            "Tags": ", ".join(d.get("tags", [])),
        })
    return output.getvalue()


def obsidian_zip(path: Path, documents: list[dict]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for d in documents:
            md = d.get("metadata") or {}
            front = {
                "type": md.get("document_type"), "issuer": md.get("issuer"), "date": md.get("document_date"),
                "deadline": md.get("deadline"), "category": d.get("category"), "profile": d.get("profile"),
                "case": d.get("case_name"), "action": d.get("action_required"), "tags": d.get("tags", []),
            }
            yaml = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items())
            body = f"---\n{yaml}\n---\n\n# {d.get('source_name')}\n\nSource: `{d.get('path')}`\n\n## Extracted text\n\n{d.get('extracted_text','')[:8000]}\n"
            name = f"{d.get('id','x')}-{_safe(d.get('source_name','document'))}.md"
            z.writestr(name, body)
    return path


def backup_zip(path: Path, state_dir: Path, documents: list[dict]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        db = state_dir / "docpilot.sqlite3"
        if db.exists():
            z.write(db, "state/docpilot.sqlite3")
        z.writestr("documents.json", json.dumps(documents, ensure_ascii=False, indent=2, default=str))
        z.writestr("README.txt", "DocPilot backup. Contains local index metadata, not source documents.\n")
    return path



def full_archive_backup(path: Path, state_dir: Path, documents: list[dict]) -> Path:
    """Portable backup with index metadata plus copies of currently accessible source files.

    Files outside the DocPilot archive are copied into source-files/ using a
    collision-safe ID prefix. Missing/unreadable sources are recorded in the
    manifest rather than aborting the whole backup.
    """
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "documents": [], "missing": []}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        db = state_dir / "docpilot.sqlite3"
        if db.exists():
            z.write(db, "state/docpilot.sqlite3")
        for d in documents:
            source = Path(str(d.get("path") or ""))
            entry = {"id": d.get("id"), "name": d.get("source_name"), "original_path": str(source)}
            if source.exists() and source.is_file():
                arcname = f"source-files/{d.get('id','x')}-{_safe(source.name)}"
                try:
                    z.write(source, arcname)
                    entry["backup_path"] = arcname
                except Exception as exc:
                    manifest["missing"].append({"path": str(source), "error": str(exc)})
            else:
                manifest["missing"].append({"path": str(source), "error": "source not found"})
            manifest["documents"].append(entry)
        z.writestr("documents.json", json.dumps(documents, ensure_ascii=False, indent=2, default=str))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        z.writestr("README.txt", "DocPilot full archive backup. Contains local index metadata and accessible source-document copies.\n")
    return path


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in str(name))[:100]
