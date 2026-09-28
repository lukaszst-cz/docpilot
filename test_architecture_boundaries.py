from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parent
CORE_MODULES = [
    "analyze.py",
    "db.py",
    "db_maintenance.py",
    "storage.py",
    "rules.py",
    "semantic.py",
    "review.py",
    "qa.py",
    "portable_config.py",
    "exporters.py",
    "update_safety.py",
]
FORBIDDEN_TOP_LEVEL_IMPORTS = {
    "fastapi",
    "uvicorn",
    "webview",
    "pywebview",
}
FORBIDDEN_DOCPILOT_MODULES = {
    "docpilot.app",
    "docpilot.desktop",
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(node.module)
    return found


def test_core_modules_do_not_depend_on_api_or_desktop_layers():
    violations: list[str] = []

    for filename in CORE_MODULES:
        path = ROOT / filename
        assert path.exists(), f"Missing documented core module: {filename}"
        for imported in _imports(path):
            top_level = imported.split(".", 1)[0]
            if top_level in FORBIDDEN_TOP_LEVEL_IMPORTS:
                violations.append(f"{filename} -> {imported}")
            if imported in FORBIDDEN_DOCPILOT_MODULES:
                violations.append(f"{filename} -> {imported}")

    assert violations == [], "Core layer dependency violations: " + ", ".join(violations)


def test_architecture_document_lists_the_enforced_core_modules():
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")

    for filename in CORE_MODULES:
        assert f"`{filename}`" in architecture
