from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .analyze import analyze_file
from .lifepilot import next_action_for_document

_SUPPORTED_SUFFIXES = {
    ".txt", ".md", ".csv", ".json", ".log", ".xml", ".html",
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp",
}


@dataclass(frozen=True)
class PilotResult:
    private_report: Path
    public_report: Path
    markdown_report: Path
    processed: int
    failed: int


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _bucket_size(size_bytes: int) -> str:
    if size_bytes < 100 * 1024:
        return "<100KB"
    if size_bytes < 1024 * 1024:
        return "100KB-1MB"
    if size_bytes < 10 * 1024 * 1024:
        return "1-10MB"
    if size_bytes < 50 * 1024 * 1024:
        return "10-50MB"
    return ">=50MB"


def _relative_files(source_dir: Path) -> list[Path]:
    files = [
        path for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    ]
    return sorted(files, key=lambda path: str(path.relative_to(source_dir)).lower())


def _private_entry(sample_id: str, source_dir: Path, path: Path, analysis: Any, life: dict[str, Any]) -> dict[str, Any]:
    payload = analysis.model_dump(mode="json")
    metadata = payload.get("metadata") or {}
    return {
        "sample_id": sample_id,
        "relative_name": str(path.relative_to(source_dir)),
        "extension": path.suffix.lower(),
        "size_bytes": int(payload.get("size_bytes") or 0),
        "sha256": payload.get("sha256"),
        "document_type": metadata.get("document_type"),
        "issuer": metadata.get("issuer"),
        "amount": metadata.get("amount"),
        "currency": metadata.get("currency"),
        "document_date": metadata.get("document_date"),
        "deadline": metadata.get("deadline"),
        "warranty_until": metadata.get("warranty_until"),
        "confidence": metadata.get("confidence"),
        "suggested_category": payload.get("suggested_category"),
        "suggested_case": payload.get("suggested_case"),
        "action_required": payload.get("action_required"),
        "health_score": payload.get("health_score"),
        "health_notes": payload.get("health_notes") or [],
        "warnings": payload.get("warnings") or [],
        "sensitive_findings": len(payload.get("sensitive") or []),
        "next_action": {
            "title": life.get("title"),
            "priority": life.get("priority"),
            "due_date": life.get("due_date"),
            "action_code": life.get("action_code"),
            "reason": life.get("reason"),
            "verification": life.get("verification"),
        },
    }


def _public_entry(private: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": private["sample_id"],
        "extension": private["extension"],
        "size_bucket": _bucket_size(int(private.get("size_bytes") or 0)),
        "document_type": private.get("document_type"),
        "has_issuer": bool(private.get("issuer")),
        "has_amount": private.get("amount") is not None,
        "has_document_date": bool(private.get("document_date")),
        "has_deadline": bool(private.get("deadline") or private.get("warranty_until")),
        "confidence": private.get("confidence"),
        "health_score": private.get("health_score"),
        "action_required": private.get("action_required"),
        "next_action": {
            "priority": (private.get("next_action") or {}).get("priority"),
            "action_code": (private.get("next_action") or {}).get("action_code"),
            "has_due_date": bool((private.get("next_action") or {}).get("due_date")),
        },
        "warning_count": len(private.get("warnings") or []),
        "health_note_count": len(private.get("health_notes") or []),
        "sensitive_finding_count": int(private.get("sensitive_findings") or 0),
    }


def _markdown(public_payload: dict[str, Any]) -> str:
    lines = [
        "# LifePilot — lokalny raport pilota",
        "",
        f"- Wygenerowano: {public_payload['generated_at']}",
        f"- Przetworzono: {public_payload['processed']}",
        f"- Błędy analizy: {public_payload['failed']}",
        "- Raport publiczny nie zawiera nazw plików, lokalnych ścieżek, pełnego OCR, issuerów, kwot ani hashy.",
        "",
        "## Wyniki techniczne",
        "",
        "| ID | Typ | Confidence | Health | Akcja | Priorytet | Termin? | Ostrzeżenia |",
        "| --- | --- | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for item in public_payload["samples"]:
        life = item.get("next_action") or {}
        confidence = item.get("confidence")
        confidence_text = f"{float(confidence):.2f}" if confidence is not None else "—"
        health = item.get("health_score")
        health_text = str(health) if health is not None else "—"
        lines.append(
            f"| {item['sample_id']} | {item.get('document_type') or '—'} | {confidence_text} | "
            f"{health_text} | {item.get('action_required') or '—'} | "
            f"{life.get('priority') or '—'} | {'tak' if life.get('has_due_date') else 'nie'} | "
            f"{item.get('warning_count') or 0} |"
        )
    if public_payload["failures"]:
        lines += ["", "## Błędy techniczne", ""]
        for failure in public_payload["failures"]:
            lines.append(f"- {failure['sample_id']}: {failure['error_type']}")

    lines += [
        "",
        "## Ręczna akceptacja — uzupełnić lokalnie",
        "",
        "Dla każdej próbki porównaj wynik z oryginałem i zaznacz:",
        "- [ ] typ dokumentu poprawny;",
        "- [ ] wystawca poprawny;",
        "- [ ] kwota/waluta poprawna, jeśli występuje;",
        "- [ ] data dokumentu poprawna;",
        "- [ ] termin/gwarancja poprawne;",
        "- [ ] „Co teraz?” i priorytet są sensowne;",
        "- [ ] niski confidence prowadzi do review-first;",
        "- [ ] korekta pól przelicza rekomendację;",
        "- [ ] Decision Trail pokazuje zmianę bez OCR/ścieżki lokalnej;",
        "- [ ] Case Readiness odpowiada kompletności materiału;",
        "- [ ] ProofPack/CasePack przechodzi lokalną weryfikację;",
        "- [ ] nie zaobserwowano niezamierzonej wysyłki danych do chmury.",
        "",
        "## Prywatność",
        "",
        "Plik pilot-private.json jest przeznaczony wyłącznie do lokalnej pracy i może zawierać "
        "nazwy względne, issuerów, kwoty oraz hashe. Nie publikuj go w publicznym repozytorium.",
        "Plik pilot-public.json i ten raport są celowo zredukowane, ale przed publikacją nadal "
        "należy je przeczytać i potwierdzić, że nie zawierają danych wrażliwych.",
        "",
    ]
    return "\n".join(lines)


def run_pilot(source_dir: Path, output_dir: Path, *, today: date | None = None) -> PilotResult:
    source_dir = source_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"Pilot source directory does not exist: {source_dir}")
    if source_dir == output_dir or output_dir.is_relative_to(source_dir):
        raise ValueError("Pilot output directory must be outside the source directory.")
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _relative_files(source_dir)
    generated_at = datetime.now(timezone.utc).isoformat()
    private_samples: list[dict[str, Any]] = []
    public_samples: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for index, path in enumerate(files, start=1):
        sample_id = f"S{index:03d}"
        try:
            analysis = analyze_file(path)
            life = next_action_for_document(analysis.model_dump(mode="json"), today=today)
            private = _private_entry(sample_id, source_dir, path, analysis, life)
            private_samples.append(private)
            public_samples.append(_public_entry(private))
        except Exception as exc:
            failures.append(
                {
                    "sample_id": sample_id,
                    "relative_name": str(path.relative_to(source_dir)),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    private_payload = {
        "format": "lifepilot-pilot-private",
        "version": 1,
        "generated_at": generated_at,
        "source_root_name": source_dir.name,
        "processed": len(private_samples),
        "failed": len(failures),
        "samples": private_samples,
        "failures": failures,
        "privacy": {
            "contains_extracted_text": False,
            "contains_absolute_paths": False,
            "publish_publicly": False,
        },
    }
    public_payload = {
        "format": "lifepilot-pilot-public",
        "version": 1,
        "generated_at": generated_at,
        "processed": len(public_samples),
        "failed": len(failures),
        "samples": public_samples,
        "failures": [
            {"sample_id": item["sample_id"], "error_type": item["error_type"]}
            for item in failures
        ],
        "privacy": {
            "contains_filenames": False,
            "contains_extracted_text": False,
            "contains_paths": False,
            "contains_issuer_values": False,
            "contains_amount_values": False,
            "contains_hashes": False,
        },
    }

    private_path = output_dir / "pilot-private.json"
    public_path = output_dir / "pilot-public.json"
    markdown_path = output_dir / "pilot-report.md"
    private_path.write_text(json.dumps(_json_safe(private_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    public_path.write_text(json.dumps(_json_safe(public_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(public_payload), encoding="utf-8")
    return PilotResult(
        private_report=private_path,
        public_report=public_path,
        markdown_report=markdown_path,
        processed=len(private_samples),
        failed=len(failures),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docpilot-pilot",
        description="Run a local LifePilot acceptance pass without uploading source documents.",
    )
    parser.add_argument("source_dir", type=Path, help="Folder containing local pilot documents.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("lifepilot-pilot-results"),
        help="Output folder outside the source folder (default: ./lifepilot-pilot-results).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_pilot(args.source_dir, args.output)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc))
    print(f"LifePilot pilot: {result.processed} processed, {result.failed} failed")
    print(f"Private report: {result.private_report}")
    print(f"Public report:  {result.public_report}")
    print(f"Markdown:       {result.markdown_report}")
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
