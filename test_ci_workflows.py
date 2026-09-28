from pathlib import Path


ROOT = Path(__file__).parent


def test_ci_uses_resilient_python_install_commands():
    test_workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    windows_workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")

    assert "python -m pip install --retries 10 --timeout 60 -e '.[dev]'" in test_workflow
    assert "python -m pytest -q" in test_workflow

    assert "python -m pip install --retries 10 --timeout 60 -e '.[full,dev]'" in windows_workflow
    assert "DocPilot dependency installation failed." in windows_workflow
    assert "python -m pip install --retries 10 --timeout 60 pyinstaller" in windows_workflow
    assert "PyInstaller installation failed." in windows_workflow
    assert "python -m pytest -q" in windows_workflow
