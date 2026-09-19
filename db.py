from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import Settings
from .models import FileAnalysis

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    extracted_text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL,
    category TEXT NOT NULL,
    suggested_filename TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    profile TEXT NOT NULL DEFAULT 'Home',
    case_name TEXT,
    action_required TEXT,
    health_score INTEGER NOT NULL DEFAULT 100,
    health_json TEXT NOT NULL DEFAULT '[]',
    simhash TEXT,
    indexed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_name);
CREATE INDEX IF NOT EXISTS idx_documents_profile ON documents(profile);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    target_category TEXT,
    target_profile TEXT,
    target_tags_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS custom_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    keywords_json TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Documents'
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def init_db(settings: Settings) -> Path:
    path = settings.state / "docpilot.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


@contextmanager
def connect(settings: Settings):
    path = init_db(settings)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def audit(settings: Settings, event: str, payload: dict[str, Any]) -> None:
    with connect(settings) as conn:
        conn.execute(
            "INSERT INTO audit(created_at,event,payload_json) VALUES(?,?,?)",
            (datetime.now(timezone.utc).isoformat(), event, _dumps(payload)),
        )


def upsert_document(
    settings: Settings,
    analysis: FileAnalysis,
    *,
    profile: str = "Home",
    case_name: str | None = None,
    tags: list[str] | None = None,
    action_required: str | None = None,
    health_score: int = 100,
    health: list[str] | None = None,
    simhash: str | None = None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    payload = (
        analysis.source_path,
        analysis.source_name,
        analysis.sha256,
        analysis.size_bytes,
        analysis.extracted_text,
        analysis.metadata.model_dump_json(),
        analysis.suggested_category,
        analysis.suggested_filename,
        _dumps(tags or []),
        profile,
        case_name,
        action_required,
        int(health_score),
        _dumps(health or []),
        simhash,
        now,
        now,
    )
    with connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO documents(
                path,source_name,sha256,size_bytes,extracted_text,metadata_json,category,
                suggested_filename,tags_json,profile,case_name,action_required,health_score,
                health_json,simhash,indexed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                source_name=excluded.source_name, sha256=excluded.sha256,
                size_bytes=excluded.size_bytes, extracted_text=excluded.extracted_text,
                metadata_json=excluded.metadata_json, category=excluded.category,
                suggested_filename=excluded.suggested_filename, tags_json=excluded.tags_json,
                profile=excluded.profile, case_name=excluded.case_name,
                action_required=excluded.action_required, health_score=excluded.health_score,
                health_json=excluded.health_json, simhash=excluded.simhash,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        row = conn.execute("SELECT id FROM documents WHERE path=?", (analysis.source_path,)).fetchone()
        return int(row["id"])


def row_to_document(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in ("metadata_json", "tags_json", "health_json"):
        try:
            parsed = json.loads(data.pop(key))
        except Exception:
            parsed = {} if key == "metadata_json" else []
        data[key.removesuffix("_json")] = parsed
    return data


def list_documents(settings: Settings, limit: int = 500) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [row_to_document(r) for r in rows]


def get_document(settings: Settings, doc_id: int) -> dict[str, Any] | None:
    with connect(settings) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return row_to_document(row) if row else None


def update_document_fields(settings: Settings, doc_id: int, **fields: Any) -> None:
    allowed = {"category", "profile", "case_name", "action_required"}
    actual = {k: v for k, v in fields.items() if k in allowed}
    if not actual:
        return
    actual["updated_at"] = datetime.now(timezone.utc).isoformat()
    columns = ",".join(f"{k}=?" for k in actual)
    with connect(settings) as conn:
        conn.execute(f"UPDATE documents SET {columns} WHERE id=?", (*actual.values(), doc_id))


def search_documents(settings: Settings, terms: list[str], limit: int = 50) -> list[dict[str, Any]]:
    if not terms:
        return list_documents(settings, limit)
    clauses = []
    params: list[Any] = []
    for term in terms:
        clauses.append("(lower(source_name) LIKE ? OR lower(extracted_text) LIKE ? OR lower(metadata_json) LIKE ? OR lower(tags_json) LIKE ? OR lower(case_name) LIKE ?)")
        pattern = f"%{term.lower()}%"
        params.extend([pattern] * 5)
    sql = "SELECT * FROM documents WHERE " + " OR ".join(clauses) + " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with connect(settings) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_document(r) for r in rows]


def list_audit(settings: Settings, limit: int = 200) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d.pop("payload_json"))
        except Exception:
            d["payload"] = {}
        out.append(d)
    return out


def list_rules(settings: Settings) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute("SELECT * FROM rules ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["condition"] = json.loads(d.pop("condition_json"))
        d["target_tags"] = json.loads(d.pop("target_tags_json"))
        d["enabled"] = bool(d["enabled"])
        out.append(d)
    return out


def add_rule(settings: Settings, payload: dict[str, Any]) -> int:
    with connect(settings) as conn:
        cur = conn.execute(
            "INSERT INTO rules(name,condition_json,target_category,target_profile,target_tags_json,enabled) VALUES(?,?,?,?,?,1)",
            (
                payload.get("name") or "Rule",
                _dumps(payload.get("condition") or {}),
                payload.get("target_category"),
                payload.get("target_profile"),
                _dumps(payload.get("target_tags") or []),
            ),
        )
        return int(cur.lastrowid)


def add_custom_type(settings: Settings, name: str, keywords: list[str], category: str) -> int:
    with connect(settings) as conn:
        cur = conn.execute(
            "INSERT INTO custom_types(name,keywords_json,category) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET keywords_json=excluded.keywords_json, category=excluded.category",
            (name, _dumps(keywords), category),
        )
        row = conn.execute("SELECT id FROM custom_types WHERE name=?", (name,)).fetchone()
        return int(row["id"])


def list_custom_types(settings: Settings) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute("SELECT * FROM custom_types ORDER BY name").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["keywords"] = json.loads(d.pop("keywords_json"))
        out.append(d)
    return out


def set_setting(settings: Settings, key: str, value: str) -> None:
    with connect(settings) as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_setting(settings: Settings, key: str, default: str | None = None) -> str | None:
    with connect(settings) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def delete_document_by_path(settings: Settings, path: str) -> None:
    with connect(settings) as conn:
        conn.execute("DELETE FROM documents WHERE path=?", (path,))


def duplicate_groups(settings: Settings) -> list[dict[str, Any]]:
    docs = list_documents(settings, limit=5000)
    groups: list[dict[str, Any]] = []
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for d in docs:
        by_hash.setdefault(d.get("sha256") or "", []).append(d)
    used: set[int] = set()
    for sha, items in by_hash.items():
        if sha and len(items) > 1:
            groups.append({"kind": "exact", "score": 1.0, "documents": items})
            used.update(int(x["id"]) for x in items)
    # Near duplicates use local simhash; avoid O(n^2) explosion by limiting to recent 500.
    recent = [d for d in docs[:500] if int(d["id"]) not in used and d.get("simhash")]
    from .intelligence import hamming_hex
    for i, a in enumerate(recent):
        near = [a]
        for b in recent[i + 1:]:
            if hamming_hex(a.get("simhash"), b.get("simhash")) <= 5:
                near.append(b)
        if len(near) > 1:
            ids = {int(x["id"]) for x in near}
            if not ids & used:
                groups.append({"kind": "near", "score": 0.9, "documents": near})
                used.update(ids)
    return groups
