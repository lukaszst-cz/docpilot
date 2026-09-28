from __future__ import annotations

import os
import shutil
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CURRENT_SCHEMA_VERSION = 1
MAX_RECOVERY_CHECKPOINTS = 5
MAX_PRE_RESTORE_BACKUPS = 5
DATABASE_LOCK = threading.RLock()


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0] if row else 0)


def _migration_backup(path: Path, conn: sqlite3.Connection, from_version: int, to_version: int) -> Path:
    backup_dir = path.parent / "migration-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"docpilot-schema-v{from_version}-to-v{to_version}-{stamp}.sqlite3"
    with closing(sqlite3.connect(backup_path)) as destination:
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
    backup_dir = path.parent / "migration-backups"
    backups = len(list(backup_dir.glob("*.sqlite3"))) if backup_dir.exists() else 0

    if not path.exists():
        return {
            "status": "missing",
            "integrity": "missing",
            "schema_version": 0,
            "supported_schema_version": CURRENT_SCHEMA_VERSION,
            "size_bytes": 0,
            "journal_mode": None,
            "migration_backups": backups,
        }

    try:
        with closing(sqlite3.connect(path)) as conn:
            integrity_row = conn.execute("PRAGMA quick_check").fetchone()
            integrity = str(integrity_row[0] if integrity_row else "unknown")
            version = schema_version(conn)
            journal_row = conn.execute("PRAGMA journal_mode").fetchone()
            journal_mode = str(journal_row[0] if journal_row else "") or None
    except sqlite3.DatabaseError:
        return {
            "status": "attention",
            "integrity": "unreadable",
            "schema_version": None,
            "supported_schema_version": CURRENT_SCHEMA_VERSION,
            "size_bytes": path.stat().st_size,
            "journal_mode": None,
            "migration_backups": backups,
        }

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
    with closing(sqlite3.connect(path)) as conn:
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


def _recovery_kind(path: Path, folder_name: str) -> str:
    if folder_name == "migration-backups":
        return "migration"
    if path.name.startswith("docpilot-pre-restore-corrupt-"):
        return "pre-restore-corrupt"
    if path.name.startswith("docpilot-pre-restore-"):
        return "pre-restore"
    return "checkpoint"


def list_recovery_points(state_dir: Path) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for folder_name in ("recovery", "migration-backups"):
        folder = state_dir / folder_name
        if not folder.exists():
            continue
        for path in folder.glob("*.sqlite3"):
            kind = _recovery_kind(path, folder_name)
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
    with DATABASE_LOCK:
        if not path.exists():
            raise FileNotFoundError(path)

        current = database_health(path)
        if current["integrity"].lower() != "ok":
            raise RuntimeError("Database integrity check failed; recovery checkpoint was not created.")

        recovery_dir = path.parent / "recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        checkpoint = recovery_dir / f"docpilot-checkpoint-{stamp}.sqlite3"

        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(checkpoint)) as destination:
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


def _resolve_recovery_point(state_dir: Path, name: str) -> tuple[Path, str]:
    clean_name = Path(str(name)).name
    if not clean_name or clean_name != str(name):
        raise ValueError("Invalid recovery point name")

    for folder_name in ("recovery", "migration-backups"):
        candidate = state_dir / folder_name / clean_name
        if candidate.exists() and candidate.is_file():
            return candidate, _recovery_kind(candidate, folder_name)
    raise FileNotFoundError(clean_name)


def _prune_pre_restore_backups(recovery_dir: Path) -> None:
    old = sorted(
        recovery_dir.glob("docpilot-pre-restore-*.sqlite3"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale in old[MAX_PRE_RESTORE_BACKUPS:]:
        stale.unlink(missing_ok=True)


def restore_database_from_point(
    path: Path,
    name: str,
    schema_sql: str,
) -> dict[str, Any]:
    state_dir = path.parent
    with DATABASE_LOCK:
        source_path, source_kind = _resolve_recovery_point(state_dir, name)
        source_meta = _checkpoint_metadata(source_path, source_kind)
        if source_meta["integrity"].lower() != "ok":
            raise RuntimeError("Recovery point failed SQLite integrity check.")
        source_version = int(source_meta["schema_version"] or 0)
        if source_version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Recovery point schema v{source_version} is newer than supported v{CURRENT_SCHEMA_VERSION}."
            )

        recovery_dir = state_dir / "recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        pre_restore_path = recovery_dir / f"docpilot-pre-restore-{stamp}.sqlite3"

        if path.exists():
            try:
                current = database_health(path)
            except sqlite3.DatabaseError:
                current = {"integrity": "unreadable"}

            if str(current.get("integrity", "")).lower() == "ok":
                with closing(sqlite3.connect(path)) as current_db, closing(sqlite3.connect(pre_restore_path)) as safety:
                    current_db.backup(safety)
                safety_meta = _checkpoint_metadata(pre_restore_path, "pre-restore")
                if safety_meta["integrity"].lower() != "ok":
                    pre_restore_path.unlink(missing_ok=True)
                    raise RuntimeError("Pre-restore safety backup verification failed.")
            else:
                corrupt_path = recovery_dir / f"docpilot-pre-restore-corrupt-{stamp}.sqlite3"
                shutil.copy2(path, corrupt_path)
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(str(path) + suffix)
                    if sidecar.exists():
                        shutil.copy2(sidecar, Path(str(corrupt_path) + suffix))
                stat = corrupt_path.stat()
                safety_meta = {
                    "name": corrupt_path.name,
                    "kind": "pre-restore-corrupt",
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "schema_version": None,
                    "integrity": "unreadable",
                }
        else:
            safety_meta = None

        temp_path = state_dir / "docpilot.restore.tmp.sqlite3"
        temp_path.unlink(missing_ok=True)
        try:
            with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(temp_path)) as destination:
                source.backup(destination)
            with closing(sqlite3.connect(temp_path)) as restored:
                migrate_database(temp_path, restored, schema_sql, backup_existing=False)
                restored.commit()

            temp_health = database_health(temp_path)
            if temp_health["integrity"].lower() != "ok":
                raise RuntimeError("Restored database failed verification before activation.")

            for suffix in ("-wal", "-shm"):
                Path(str(path) + suffix).unlink(missing_ok=True)
            os.replace(temp_path, path)

            active = database_health(path)
            if active["integrity"].lower() != "ok":
                raise RuntimeError("Restored database failed verification after activation.")
        finally:
            temp_path.unlink(missing_ok=True)

        _prune_pre_restore_backups(recovery_dir)
        return {
            "restored_from": source_meta,
            "pre_restore_backup": safety_meta,
            "database": database_health(path),
        }
