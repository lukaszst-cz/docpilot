from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import Settings
from .db_maintenance import DATABASE_LOCK, migrate_database
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
CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at DESC, id DESC);
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
CREATE TABLE IF NOT EXISTS integration_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    scope_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    attempted INTEGER NOT NULL DEFAULT 0,
    succeeded INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_integration_runs_provider_started
    ON integration_runs(provider, started_at DESC);
CREATE TABLE IF NOT EXISTS integration_links (
    provider TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    external_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(provider, document_id)
);
CREATE INDEX IF NOT EXISTS idx_integration_links_external
    ON integration_links(provider, external_id);
"""


def init_db(settings: Settings) -> Path:
    path = settings.state / "docpilot.sqlite3"
    with DATABASE_LOCK:
        existed = path.exists() and path.stat().st_size > 0
        with sqlite3.connect(path) as conn:
            migrate_database(path, conn, SCHEMA, backup_existing=existed)
    return path


@contextmanager
def connect(settings: Settings):
    with DATABASE_LOCK:
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


def start_integration_run(
    settings: Settings,
    provider: str,
    operation: str,
    scope: dict[str, Any] | None = None,
) -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    with connect(settings) as conn:
        cur = conn.execute(
            """
            INSERT INTO integration_runs(
                provider,operation,scope_json,status,started_at
            ) VALUES(?,?,?,?,?)
            """,
            (provider, operation, _dumps(scope or {}), "running", started_at),
        )
        return int(cur.lastrowid)


def finish_integration_run(
    settings: Settings,
    run_id: int,
    *,
    status: str,
    attempted: int = 0,
    succeeded: int = 0,
    skipped: int = 0,
    failed: int = 0,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc).isoformat()
    with connect(settings) as conn:
        conn.execute(
            """
            UPDATE integration_runs
            SET status=?,attempted=?,succeeded=?,skipped=?,failed=?,errors_json=?,completed_at=?
            WHERE id=?
            """,
            (
                status,
                int(attempted),
                int(succeeded),
                int(skipped),
                int(failed),
                _dumps(errors or []),
                completed_at,
                run_id,
            ),
        )
        row = conn.execute("SELECT * FROM integration_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise KeyError(run_id)
    data = dict(row)
    data["scope"] = json.loads(data.pop("scope_json"))
    data["errors"] = json.loads(data.pop("errors_json"))
    return data


def list_integration_runs(
    settings: Settings,
    *,
    provider: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = min(max(int(limit), 1), 200)
    with connect(settings) as conn:
        if provider.strip():
            rows = conn.execute(
                "SELECT * FROM integration_runs WHERE provider=? ORDER BY id DESC LIMIT ?",
                (provider.strip(), safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM integration_runs ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
    out = []
    for row in rows:
        data = dict(row)
        data["scope"] = json.loads(data.pop("scope_json"))
        data["errors"] = json.loads(data.pop("errors_json"))
        out.append(data)
    return out


def list_documents_for_integration(
    settings: Settings,
    *,
    limit: int = 100,
    profile: str = "",
    case_name: str = "",
    action_required: str = "",
    category: str = "",
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[str] = []
    params: list[Any] = []

    if profile.strip():
        clauses.append("profile=?")
        params.append(profile.strip())
    if case_name.strip():
        clauses.append("case_name=?")
        params.append(case_name.strip())
    if action_required.strip():
        clauses.append("action_required=?")
        params.append(action_required.strip())
    if category.strip():
        clauses.append("category LIKE ?")
        params.append(f"{category.strip()}%")

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    safe_limit = min(max(int(limit), 1), 500)
    with connect(settings) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM documents{where}", params).fetchone()[0])
        rows = conn.execute(
            f"SELECT * FROM documents{where} ORDER BY updated_at DESC, id DESC LIMIT ?",
            (*params, safe_limit),
        ).fetchall()
    return [row_to_document(row) for row in rows], total


def get_integration_link(settings: Settings, provider: str, document_id: int) -> dict[str, Any] | None:
    with connect(settings) as conn:
        row = conn.execute(
            "SELECT * FROM integration_links WHERE provider=? AND document_id=?",
            (provider, int(document_id)),
        ).fetchone()
    return dict(row) if row else None


def upsert_integration_link(
    settings: Settings,
    *,
    provider: str,
    document_id: int,
    external_id: str,
    fingerprint: str,
    external_url: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO integration_links(
                provider,document_id,external_id,fingerprint,external_url,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(provider,document_id) DO UPDATE SET
                external_id=excluded.external_id,
                fingerprint=excluded.fingerprint,
                external_url=excluded.external_url,
                updated_at=excluded.updated_at
            """,
            (provider, int(document_id), external_id, fingerprint, external_url, now, now),
        )
        row = conn.execute(
            "SELECT * FROM integration_links WHERE provider=? AND document_id=?",
            (provider, int(document_id)),
        ).fetchone()
    return dict(row)


def delete_integration_link(settings: Settings, provider: str, document_id: int) -> None:
    with connect(settings) as conn:
        conn.execute(
            "DELETE FROM integration_links WHERE provider=? AND document_id=?",
            (provider, int(document_id)),
        )


def list_integration_links(
    settings: Settings,
    *,
    provider: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    safe_limit = min(max(int(limit), 1), 5000)
    with connect(settings) as conn:
        if provider.strip():
            rows = conn.execute(
                "SELECT * FROM integration_links WHERE provider=? ORDER BY updated_at DESC LIMIT ?",
                (provider.strip(), safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM integration_links ORDER BY updated_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
    return [dict(row) for row in rows]


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


def list_document_page(
    settings: Settings,
    *,
    limit: int = 100,
    offset: int = 0,
    query: str = "",
    profile: str = "",
    case_name: str = "",
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[str] = []
    params: list[Any] = []

    if query.strip():
        pattern = f"%{query.strip().lower()}%"
        clauses.append(
            "(lower(source_name) LIKE ? OR lower(category) LIKE ? OR lower(case_name) LIKE ? "
            "OR lower(profile) LIKE ? OR lower(metadata_json) LIKE ?)"
        )
        params.extend([pattern] * 5)
    if profile.strip():
        clauses.append("profile = ?")
        params.append(profile.strip())
    if case_name.strip():
        clauses.append("case_name = ?")
        params.append(case_name.strip())

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    select_columns = """
        id, path, source_name, metadata_json, category, tags_json, profile,
        case_name, action_required, health_score, health_json, indexed_at, updated_at
    """
    with connect(settings) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM documents{where}", params).fetchone()[0])
        rows = conn.execute(
            f"SELECT {select_columns} FROM documents{where} "
            "ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [row_to_document(row) for row in rows], total


def dashboard_summary(settings: Settings) -> dict[str, Any]:
    with connect(settings) as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS documents,
                SUM(CASE WHEN action_required IS NOT NULL AND action_required <> '' THEN 1 ELSE 0 END) AS actions,
                SUM(CASE WHEN health_score < 70 THEN 1 ELSE 0 END) AS unhealthy,
                COUNT(DISTINCT CASE WHEN case_name IS NOT NULL AND case_name <> '' THEN case_name END) AS cases
            FROM documents
            """
        ).fetchone()
        profiles = [
            row["profile"] or "Home"
            for row in conn.execute("SELECT DISTINCT profile FROM documents ORDER BY profile").fetchall()
        ]
        deadline_rows = conn.execute(
            """
            SELECT id, source_name, metadata_json, action_required
            FROM documents
            WHERE metadata_json LIKE '%"deadline":%'
               OR metadata_json LIKE '%"warranty_until":%'
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

    deadlines: list[dict[str, Any]] = []
    today = date.today()
    for row in deadline_rows:
        try:
            metadata = json.loads(row["metadata_json"])
        except Exception:
            metadata = {}
        value = metadata.get("deadline") or metadata.get("warranty_until")
        if not value:
            continue
        try:
            day = date.fromisoformat(str(value))
        except ValueError:
            continue
        delta = (day - today).days
        if delta >= -7:
            deadlines.append(
                {
                    "id": int(row["id"]),
                    "name": row["source_name"],
                    "date": day.isoformat(),
                    "days": delta,
                    "action": row["action_required"],
                }
            )
    deadlines.sort(key=lambda item: item["date"])
    return {
        "documents": int(totals["documents"] or 0),
        "actions": int(totals["actions"] or 0),
        "unhealthy": int(totals["unhealthy"] or 0),
        "cases": int(totals["cases"] or 0),
        "profiles": profiles,
        "deadlines": deadlines[:40],
        "deadline_count": len(deadlines),
    }


def duplicate_id_groups(settings: Settings, near_limit: int = 500) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        exact_rows = conn.execute(
            """
            SELECT sha256, GROUP_CONCAT(id) AS ids
            FROM documents
            WHERE sha256 <> ''
            GROUP BY sha256
            HAVING COUNT(*) > 1
            """
        ).fetchall()
        near_rows = conn.execute(
            """
            SELECT id, simhash
            FROM documents
            WHERE simhash IS NOT NULL
              AND simhash <> ''
              AND sha256 NOT IN (
                  SELECT sha256
                  FROM documents
                  WHERE sha256 <> ''
                  GROUP BY sha256
                  HAVING COUNT(*) > 1
              )
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (min(max(int(near_limit), 50), 1000),),
        ).fetchall()

    groups: list[dict[str, Any]] = []
    for row in exact_rows:
        ids = [int(value) for value in str(row["ids"] or "").split(",") if value]
        if len(ids) > 1:
            groups.append({"kind": "exact", "ids": ids})

    from .intelligence import hamming_hex

    candidates = [{"id": int(row["id"]), "simhash": row["simhash"]} for row in near_rows]
    used: set[int] = set()
    for i, left in enumerate(candidates):
        left_id = int(left["id"])
        if left_id in used:
            continue
        near_ids = {left_id}
        for right in candidates[i + 1:]:
            right_id = int(right["id"])
            if right_id in used:
                continue
            if hamming_hex(left["simhash"], right["simhash"]) <= 5:
                near_ids.add(right_id)
        if len(near_ids) > 1:
            ids = sorted(near_ids)
            groups.append({"kind": "near", "ids": ids})
            used.update(ids)
    return groups


def duplicate_group_count(settings: Settings) -> int:
    return len(duplicate_id_groups(settings))


def duplicate_review_groups(settings: Settings, near_limit: int = 500) -> list[dict[str, Any]]:
    return [
        {"kind": group["kind"], "documents": [{"id": doc_id} for doc_id in group["ids"]]}
        for group in duplicate_id_groups(settings, near_limit=near_limit)
    ]


def review_candidate_documents(
    settings: Settings,
    *,
    limit: int = 1500,
    duplicate_limit: int = 500,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from .review import DEADLINE_HINTS

    safe_limit = min(max(int(limit), 100), 2500)
    duplicate_groups = duplicate_review_groups(settings, near_limit=500)

    hint_clause = " OR ".join("lower(extracted_text) LIKE ?" for _ in DEADLINE_HINTS)
    hint_params = [f"%{hint.lower()}%" for hint in DEADLINE_HINTS]
    base_limit = max(100, safe_limit - min(max(int(duplicate_limit), 0), 900))

    with connect(settings) as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM documents
            WHERE health_score < 70
               OR action_required = 'to-review'
               OR length(trim(extracted_text)) = 0
               OR COALESCE(CAST(json_extract(metadata_json, '$.confidence') AS REAL), 0) < 0.65
               OR (
                    ({hint_clause})
                    AND COALESCE(json_extract(metadata_json, '$.deadline'), '') = ''
               )
            ORDER BY health_score ASC, updated_at DESC, id DESC
            LIMIT ?
            """,
            (*hint_params, base_limit),
        ).fetchall()

        documents = [row_to_document(row) for row in rows]
        present = {int(doc["id"]) for doc in documents}

        duplicate_ids: list[int] = []
        for group in duplicate_groups:
            for item in group["documents"]:
                doc_id = int(item["id"])
                if doc_id not in present and doc_id not in duplicate_ids:
                    duplicate_ids.append(doc_id)

        room = max(0, safe_limit - len(documents))
        duplicate_ids = duplicate_ids[: min(room, 900)]
        if duplicate_ids:
            placeholders = ",".join("?" for _ in duplicate_ids)
            duplicate_rows = conn.execute(
                f"SELECT * FROM documents WHERE id IN ({placeholders})",
                duplicate_ids,
            ).fetchall()
            documents.extend(row_to_document(row) for row in duplicate_rows)

    return documents, duplicate_groups



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


def update_documents_fields(settings: Settings, doc_ids: list[int], **fields: Any) -> int:
    allowed = {"category", "profile", "case_name", "action_required"}
    actual = {k: v for k, v in fields.items() if k in allowed}
    ids = sorted({int(doc_id) for doc_id in doc_ids if int(doc_id) > 0})
    if not ids or not actual:
        return 0

    actual["updated_at"] = datetime.now(timezone.utc).isoformat()
    columns = ",".join(f"{k}=?" for k in actual)
    placeholders = ",".join("?" for _ in ids)
    with connect(settings) as conn:
        cur = conn.execute(
            f"UPDATE documents SET {columns} WHERE id IN ({placeholders})",
            (*actual.values(), *ids),
        )
        return int(cur.rowcount)


def search_documents(settings: Settings, terms: list[str], limit: int = 50) -> list[dict[str, Any]]:
    if not terms:
        return list_documents(settings, limit)

    clauses: list[str] = []
    where_params: list[Any] = []
    score_params: list[Any] = []
    for term in terms:
        clause = (
            "(lower(source_name) LIKE ? OR lower(extracted_text) LIKE ? OR lower(metadata_json) LIKE ? "
            "OR lower(tags_json) LIKE ? OR lower(case_name) LIKE ?)"
        )
        clauses.append(clause)
        pattern = f"%{term.lower()}%"
        where_params.extend([pattern] * 5)
        score_params.extend([pattern] * 5)

    score = " + ".join(f"CASE WHEN {clause} THEN 1 ELSE 0 END" for clause in clauses)
    sql = (
        "SELECT * FROM documents WHERE "
        + " OR ".join(clauses)
        + f" ORDER BY ({score}) DESC, updated_at DESC LIMIT ?"
    )
    params = [*where_params, *score_params, limit]
    with connect(settings) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_document(r) for r in rows]


def semantic_candidate_documents(
    settings: Settings,
    query: str,
    *,
    limit: int = 750,
    fallback_limit: int = 500,
) -> list[dict[str, Any]]:
    from .semantic import candidate_terms

    safe_limit = min(max(int(limit), 50), 1000)
    terms = candidate_terms(query)
    if terms:
        candidates = search_documents(settings, terms, limit=safe_limit)
        if candidates:
            return candidates

    return list_documents(settings, limit=min(max(int(fallback_limit), 50), safe_limit))


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
        rows = conn.execute("SELECT * FROM rules ORDER BY id ASC").fetchall()
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


def update_rule(settings: Settings, rule_id: int, payload: dict[str, Any]) -> bool:
    with connect(settings) as conn:
        row = conn.execute("SELECT * FROM rules WHERE id=?", (rule_id,)).fetchone()
        if not row:
            return False

        current = dict(row)
        condition = payload["condition"] if "condition" in payload else json.loads(current["condition_json"])
        target_tags = payload["target_tags"] if "target_tags" in payload else json.loads(current["target_tags_json"])
        enabled = int(bool(payload["enabled"])) if "enabled" in payload else int(current["enabled"])

        conn.execute(
            """
            UPDATE rules
            SET name=?, condition_json=?, target_category=?, target_profile=?,
                target_tags_json=?, enabled=?
            WHERE id=?
            """,
            (
                payload.get("name", current["name"]),
                _dumps(condition or {}),
                payload.get("target_category", current["target_category"]),
                payload.get("target_profile", current["target_profile"]),
                _dumps(target_tags or []),
                enabled,
                rule_id,
            ),
        )
        return True


def delete_rule(settings: Settings, rule_id: int) -> bool:
    with connect(settings) as conn:
        cur = conn.execute("DELETE FROM rules WHERE id=?", (rule_id,))
        return cur.rowcount > 0


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


def duplicate_groups(settings: Settings, documents: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    docs = documents if documents is not None else list_documents(settings, limit=5000)
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
