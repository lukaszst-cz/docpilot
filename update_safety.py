from __future__ import annotations

from typing import Any

from .config import Settings
from .db import connect, get_setting, init_db, set_setting
from .db_maintenance import create_database_checkpoint


LAST_STARTED_VERSION_KEY = "last_started_version"
LAST_UPGRADE_CHECKPOINT_KEY = "last_upgrade_checkpoint"


def _has_existing_user_state(settings: Settings) -> bool:
    with connect(settings) as conn:
        counts = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM documents) +
                (SELECT COUNT(*) FROM rules) +
                (SELECT COUNT(*) FROM custom_types) +
                (SELECT COUNT(*) FROM audit) +
                (SELECT COUNT(*) FROM integration_runs) +
                (SELECT COUNT(*) FROM settings
                 WHERE key NOT IN (?, ?))
            """,
            (LAST_STARTED_VERSION_KEY, LAST_UPGRADE_CHECKPOINT_KEY),
        ).fetchone()
    return bool(int(counts[0] if counts else 0))


def ensure_version_recovery(settings: Settings, current_version: str) -> dict[str, Any]:
    previous = get_setting(settings, LAST_STARTED_VERSION_KEY)

    if previous == current_version:
        return {
            "status": "current",
            "previous_version": previous,
            "current_version": current_version,
            "checkpoint": get_setting(settings, LAST_UPGRADE_CHECKPOINT_KEY),
        }

    if not previous and not _has_existing_user_state(settings):
        set_setting(settings, LAST_STARTED_VERSION_KEY, current_version)
        return {
            "status": "initialized",
            "previous_version": None,
            "current_version": current_version,
            "checkpoint": None,
        }

    checkpoint = create_database_checkpoint(init_db(settings))
    set_setting(settings, LAST_UPGRADE_CHECKPOINT_KEY, checkpoint["name"])
    set_setting(settings, LAST_STARTED_VERSION_KEY, current_version)
    return {
        "status": "checkpointed",
        "previous_version": previous or "legacy/unknown",
        "current_version": current_version,
        "checkpoint": checkpoint["name"],
    }
