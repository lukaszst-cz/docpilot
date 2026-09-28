import ast
from pathlib import Path

from docpilot.db_maintenance import CURRENT_SCHEMA_VERSION
from docpilot.portable_config import FORMAT_NAME, FORMAT_VERSION


ROOT = Path(__file__).parent

CORE_MODULES = [
    "analyze.py",
    "config.py",
    "db.py",
    "db_maintenance.py",
    "diffing.py",
    "exporters.py",
    "extract.py",
    "intelligence.py",
    "models.py",
    "portable_config.py",
    "preprocess.py",
    "qa.py",
    "redaction.py",
    "review.py",
    "rules.py",
    "semantic.py",
    "storage.py",
]

FORBIDDEN_ROOT_IMPORTS = {"fastapi", "uvicorn", "webview"}
FORBIDDEN_INTERNAL_IMPORTS = {"app", "desktop", "cli", "mcp_server", "notifier_entry"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
    return imports


def test_core_modules_do_not_depend_on_web_or_desktop_layers():
    violations: list[str] = []

    for name in CORE_MODULES:
        path = ROOT / name
        imports = _imports(path)
        for imported in imports:
            root = imported.split(".", 1)[0]
            internal = imported.rsplit(".", 1)[-1]
            if root in FORBIDDEN_ROOT_IMPORTS or internal in FORBIDDEN_INTERNAL_IMPORTS:
                violations.append(f"{name} -> {imported}")

    assert violations == []


def test_integrations_do_not_import_the_application_layer():
    for name in ("integrations.py", "integration_registry.py"):
        imports = _imports(ROOT / name)
        assert not any(item.endswith(".app") or item == "app" for item in imports)


def test_compatibility_formats_are_explicit_and_versioned():
    assert CURRENT_SCHEMA_VERSION >= 1
    assert FORMAT_NAME == "docpilot-portable-config"
    assert FORMAT_VERSION >= 1


def test_architecture_document_records_compatibility_boundaries():
    text = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")

    assert "SQLite schema" in text
    assert "Portable Configuration" in text
    assert "Recovery checkpoint" in text
    assert "PWA shell" in text
    assert "baza z nowszym schema jest odrzucana" in text
    assert "nieznanego formatu ma zostać odrzucony" in text
