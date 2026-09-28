from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CURRENT_SCHEMA_VERSION = 1
MAX_RECOVERY_CHECKPOINTS = 5


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0] if row else 0)


def _migration_backup(path: Path, conn: sqlite3.Connection, from_version: int, to_version: int) -> Path:
    backup_dir = path.parent / "migration-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"docpilot-schema-v{from_version}-to-v{to_version}-{stamp}.sqlite3"
    with sqlite3.connect(backup_path) as destination:
        conn.backup(destination)
    return backup_path


def migrate_database(
    path: Path,
    conn: sqlite3.Connection,
    schema_sql: str,
    *,
    backup_existing: bool,
) -> int:
    current = schema_version(conn)
    if current > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema v{current} is newer than this DocPilot build supports "
            f"(v{CURRENT_SCHEMA_VERSION})."
        )

    if current < CURRENT_SCHEMA_VERSION and backup_existing:
        _migration_backup(path, conn, current, CURRENT_SCHEMA_VERSION)

    # Version 1 is the first explicitly tracked DocPilot schema. The current
    # schema is idempotent, so legacy unversioned databases can be upgraded
    # safely while preserving existing rows.
    conn.executescript(schema_sql)

    if current < CURRENT_SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
        conn.commit()

    return CURRENT_SCHEMA_VERSION


def database_health(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "missing",
            "integrity": "missing",
            "schema_version": 0,
            "supported_schema_version": CURRENT_SCHEMA_VERSION,
            "size_bytes": 0,
            "journal_mode": None,
            "migration_backups": 0,
        }

    with sqlite3.connect(path) as conn:
        integrity_row = conn.execute("PRAGMA quick_check").fetchone()
        integrity = str(integrity_row[0] if integrity_row else "unknown")
        version = schema_version(conn)
        journal_row = conn.execute("PRAGMA journal_mode").fetchone()
        journal_mode = str(journal_row[0] if journal_row else "") or None

    backup_dir = path.parent / "migration-backups"
    backups = len(list(backup_dir.glob("*.sqlite3"))) if backup_dir.exists() else 0
    supported = version <= CURRENT_SCHEMA_VERSION and integrity.lower() == "ok"
    return {
        "status": "ok" if supported else "attention",
        "integrity": integrity,
        "schema_version": version,
        "supported_schema_version": CURRENT_SCHEMA_VERSION,
        "size_bytes": path.stat().st_size,
        "journal_mode": journal_mode,
        "migration_backups": backups,
    }


def _checkpoint_metadata(path: Path, kind: str) -> dict[str, Any]:
    with sqlite3.connect(path) as conn:
        integrity_row = conn.execute("PRAGMA quick_check").fetchone()
        integrity = str(integrity_row[0] if integrity_row else "unknown")
        version = schema_version(conn)
    stat = path.stat()
    return {
        "name": path.name,
        "kind": kind,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "schema_version": version,
        "integrity": integrity,
    }


def list_recovery_points(state_dir: Path) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for kind, folder_name in (("checkpoint", "recovery"), ("migration", "migration-backups")):
        folder = state_dir / folder_name
        if not folder.exists():
            continue
        for path in folder.glob("*.sqlite3"):
            try:
                points.append(_checkpoint_metadata(path, kind))
            except sqlite3.DatabaseError:
                stat = path.stat()
                points.append({
                    "name": path.name,
                    "kind": kind,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "schema_version": None,
                    "integrity": "unreadable",
                })
    return sorted(points, key=lambda item: item["modified_at"], reverse=True)


def create_database_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    current = database_health(path)
    if current["integrity"].lower() != "ok":
        raise RuntimeError("Database integrity check failed; recovery checkpoint was not created.")

    recovery_dir = path.parent / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    checkpoint = recovery_dir / f"docpilot-checkpoint-{stamp}.sqlite3"

    with sqlite3.connect(path) as source, sqlite3.connect(checkpoint) as destination:
        source.backup(destination)

    created = _checkpoint_metadata(checkpoint, "checkpoint")
    if created["integrity"].lower() != "ok":
        checkpoint.unlink(missing_ok=True)
        raise RuntimeError("Recovery checkpoint verification failed.")

    old = sorted(
        recovery_dir.glob("docpilot-checkpoint-*.sqlite3"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale in old[MAX_RECOVERY_CHECKPOINTS:]:
        stale.unlink(missing_ok=True)

    return created
