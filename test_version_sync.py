from pathlib import Path
import re
import tomllib

import docpilot


ROOT = Path(__file__).parent


def test_public_version_markers_are_in_sync():
    version = docpilot.__version__
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == version

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert f"v{version}" in index
    assert f"app.css?v={version}" in index
    assert f"app.js?v={version}" in index

    worker = (ROOT / "service-worker.js").read_text(encoding="utf-8")
    cache_version = version.replace(".", "")
    assert f"docpilot-shell-v{cache_version}" in worker
    assert f"app.css?v={version}" in worker
    assert f"app.js?v={version}" in worker

    for path in (ROOT / "DocPilot.iss", ROOT / "packaging" / "installer" / "DocPilot.iss"):
        content = path.read_text(encoding="utf-8")
        match = re.search(r'#define MyAppVersion "([^"]+)"', content)
        assert match
        assert match.group(1) == version
