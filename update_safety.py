from __future__ import annotations

from typing import Any

from .config import Settings
from .db import get_setting, init_db, set_setting
from .db_maintenance import create_database_checkpoint


LAST_STARTED_VERSION_KEY = "last_started_version"
LAST_UPGRADE_CHECKPOINT_KEY = "last_upgrade_checkpoint"


def ensure_version_recovery(settings: Settings, current_version: str) -> dict[str, Any]:
    previous = get_setting(settings, LAST_STARTED_VERSION_KEY)

    if previous == current_version:
        return {
            "status": "current",
            "previous_version": previous,
            "current_version": current_version,
            "checkpoint": get_setting(settings, LAST_UPGRADE_CHECKPOINT_KEY),
        }

    if not previous:
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
        "previous_version": previous,
        "current_version": current_version,
        "checkpoint": checkpoint["name"],
    }
