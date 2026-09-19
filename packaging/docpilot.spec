# PyInstaller spec for DocPilot Desktop (Windows one-folder build)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
datas += [("docpilot/templates", "docpilot/templates")]
datas += [("docpilot/static", "docpilot/static")]

hiddenimports = []
for package in [
    "uvicorn", "webview", "pytesseract", "pypdfium2", "sklearn", "keyring",
    "googleapiclient", "google_auth_oauthlib", "google.oauth2", "winotify", "mcp",
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
    ["docpilot/desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
