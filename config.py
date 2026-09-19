from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    inbox: Path
    archive: Path
    state: Path
    exports: Path
    redacted: Path
    max_upload_mb: int = 75


def _default_root() -> Path:
    override = os.environ.get("DOCPILOT_HOME")
    if override:
        return Path(override).expanduser()

    # Installed/frozen builds need a stable per-user data location. Scheduled
    # notification tasks do not inherit the app's working directory, so cwd is
    # not safe for persistent state in packaged builds.
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            return local / "DocPilot" / "Data"
        return Path.home() / ".local" / "share" / "docpilot"

    # Source/developer mode intentionally remains self-contained in the repo.
    return Path.cwd() / ".docpilot"


def get_settings(root: Path | None = None) -> Settings:
    base = (root or _default_root()).resolve()
    inbox = base / "inbox"
    archive = base / "archive"
    state = base / "state"
    exports = base / "exports"
    redacted = base / "redacted"
    for path in (base, inbox, archive, state, exports, redacted):
        path.mkdir(parents=True, exist_ok=True)
    return Settings(root=base, inbox=inbox, archive=archive, state=state, exports=exports, redacted=redacted)
