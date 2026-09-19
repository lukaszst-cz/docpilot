from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .models import AppliedChange

_WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_name(name: str) -> str:
    """Return a Windows-safe leaf filename while preserving the extension."""
    raw = Path(str(name)).name.strip()
    raw = _WINDOWS_INVALID.sub("-", raw)
    raw = re.sub(r"-{2,}", "-", raw)
    raw = raw.rstrip(" .")
    if not raw:
        raw = "document"

    p = Path(raw)
    stem = p.stem.rstrip(" .") or "document"
    suffix = p.suffix.rstrip(" .")
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"{stem}-file"

    # Stay comfortably below common Windows path component limits.
    max_stem = max(1, 180 - len(suffix))
    stem = stem[:max_stem].rstrip(" .") or "document"
    return f"{stem}{suffix}"


def safe_category(category: str) -> Path:
    raw_parts = re.split(r"[\\/]+", str(category))
    parts = [safe_name(part) for part in raw_parts if part.strip() not in {"", ".", ".."}]
    return Path(*parts) if parts else Path("Documents")


def unique_destination(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    filename = safe_name(filename)
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem, suffix = candidate.stem, candidate.suffix
    for i in range(2, 10000):
        alt = directory / f"{stem}-{i}{suffix}"
        if not alt.exists():
            return alt
    raise RuntimeError("Could not allocate a unique destination filename.")


def _same_file_identity(path: Path, *, expected_size: int) -> bool:
    try:
        return path.exists() and path.is_file() and path.stat().st_size == expected_size
    except OSError:
        return False


def apply_change(
    settings: Settings,
    source: Path,
    category: str,
    filename: str,
    mode: str = "rename",
) -> AppliedChange:
    source = source.expanduser().resolve(strict=True)
    if not source.is_file():
        raise FileNotFoundError(source)

    original_size = source.stat().st_size
    filename = safe_name(filename)

    if mode == "rename":
        if filename.casefold() == source.name.casefold():
            raise ValueError(
                "The proposed filename is the same as the current filename. "
                "Edit the filename before pressing Apply."
            )

        destination = unique_destination(source.parent, filename)

        try:
            # Direct rename is the most reliable same-folder operation on Windows.
            source.rename(destination)
        except PermissionError as exc:
            raise PermissionError(
                "Windows refused to rename the file. Close the document if it is open "
                "in another program and try again."
            ) from exc
        except OSError as exc:
            raise OSError(f"Windows rename failed: {exc}") from exc

        action = "rename"

    elif mode == "organize":
        destination = unique_destination(settings.archive / safe_category(category), filename)
        try:
            shutil.move(str(source), str(destination))
        except PermissionError as exc:
            raise PermissionError(
                "Windows refused to move the file. Close the document if it is open "
                "in another program and try again."
            ) from exc
        except OSError as exc:
            raise OSError(f"Windows move failed: {exc}") from exc
        action = "move"
    else:
        raise ValueError(f"Unsupported apply mode: {mode}")

    destination = destination.resolve()

    # Never report success unless the filesystem confirms it.
    verified = (not source.exists()) and _same_file_identity(destination, expected_size=original_size)
    if not verified:
        raise RuntimeError(
            "DocPilot could not verify the file operation. "
            f"Expected new file: {destination}"
        )

    change = AppliedChange(
        id=uuid.uuid4().hex,
        created_at=datetime.now(timezone.utc),
        action=action,
        source=str(source),
        destination=str(destination),
        verified=True,
    )
    _write_change(settings, change)
    return change


def apply_move(settings: Settings, source: Path, category: str, filename: str) -> AppliedChange:
    return apply_change(settings, source, category, filename, mode="organize")


def undo_change(settings: Settings, change_id: str) -> Path:
    path = settings.state / "changes" / f"{change_id}.json"
    if not path.exists():
        raise FileNotFoundError(change_id)

    change = AppliedChange.model_validate_json(path.read_text(encoding="utf-8"))
    destination = Path(change.destination).resolve()
    source = Path(change.source)

    if not destination.exists():
        raise FileNotFoundError(destination)

    source.parent.mkdir(parents=True, exist_ok=True)
    restored = source if not source.exists() else unique_destination(source.parent, source.name)

    if destination.parent.resolve() == restored.parent.resolve():
        destination.rename(restored)
    else:
        shutil.move(str(destination), str(restored))

    if not restored.exists():
        raise RuntimeError("Undo could not be verified on disk.")

    path.unlink(missing_ok=True)
    return restored.resolve()


def list_changes(settings: Settings) -> list[AppliedChange]:
    folder = settings.state / "changes"
    folder.mkdir(parents=True, exist_ok=True)
    changes: list[AppliedChange] = []
    for path in folder.glob("*.json"):
        try:
            changes.append(AppliedChange.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return sorted(changes, key=lambda item: item.created_at, reverse=True)


def _write_change(settings: Settings, change: AppliedChange) -> None:
    folder = settings.state / "changes"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{change.id}.json").write_text(
        json.dumps(change.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
