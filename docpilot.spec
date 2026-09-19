# PyInstaller spec for DocPilot Desktop (Windows one-folder build)
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_spec_path = Path(SPECPATH).resolve()
if _spec_path.is_file():
    _spec_path = _spec_path.parent
ROOT = _spec_path.parent if _spec_path.name.lower() == "packaging" else _spec_path

datas = [
    (str(ROOT / "sample_invoice.txt"), "docpilot/demo"),
    (str(ROOT / "index.html"), "docpilot/templates"),
    (str(ROOT / "app.css"), "docpilot/static"),
    (str(ROOT / "app.js"), "docpilot/static"),
    (str(ROOT / "manifest.webmanifest"), "docpilot/static"),
    (str(ROOT / "service-worker.js"), "docpilot/static"),
    (str(ROOT / "icon-192.png"), "docpilot/static"),
    (str(ROOT / "icon-512.png"), "docpilot/static"),
]

hiddenimports = ["docpilot.app"]
for package in [
    "uvicorn", "webview", "pytesseract", "pypdfium2", "sklearn", "keyring",
    "googleapiclient", "google_auth_oauthlib", "google.oauth2", "winotify",
]:
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

for package in ["keyring", "googleapiclient", "google_auth_oauthlib", "winotify"]:
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT.parent), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["mcp"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DocPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="DocPilot")
