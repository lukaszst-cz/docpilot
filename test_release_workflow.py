from pathlib import Path


ROOT = Path(__file__).parent


def test_windows_release_only_auto_publishes_stable_main_builds():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")

    assert "Resolve stable release version" in workflow
    assert "tomllib.loads" in workflow
    assert "$parsed = [version]$version" in workflow
    assert "Check stable release tag" in workflow
    assert "Create stable release tag" in workflow
    assert "Publish GitHub Release" in workflow
    assert "steps.release_meta.outputs.stable == 'true'" in workflow
    assert "steps.release_tag.outputs.exists == 'false'" in workflow
    assert "git tag -a $tag $env:GITHUB_SHA" in workflow
    assert "git push origin $tag" in workflow


def test_manual_tag_must_match_package_version():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")

    assert "Validate tagged release version" in workflow
    assert 'if ("${{ github.ref_name }}" -ne $expected)' in workflow


def test_windows_release_runs_functional_self_test_on_packaged_installed_and_upgraded_apps():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
    desktop = (ROOT / "desktop.py").read_text(encoding="utf-8")

    assert workflow.count("'--self-test'") >= 3
    assert "Self-test packaged DocPilot" in workflow
    assert "Clean install and uninstall smoke test" in workflow
    assert "Upgrade smoke test from stable v4.0.0" in workflow
    assert "releases/download/v4.0.0/DocPilot-Setup-Windows-x64.exe" in workflow
    assert "_lifepilot_functional_self_test()" in desktop
    assert "fastapi.testclient" not in desktop
    assert "httpx" not in desktop
    assert "TemporaryDirectory" in desktop
    assert "lifepilot_document_history" in desktop
    assert "lifepilot_case_readiness" in desktop
    assert "lifepilot_casepack" in desktop
    assert "verify_lifepilot_pack" in desktop
    assert "lifepilot_mark_done" in desktop
    assert "_lifepilot_deadline_boundary_self_test()" in desktop
    assert "_lifepilot_calendar_self_test()" in desktop
    assert "_lifepilot_recovery_self_test" in desktop
    assert "create_database_checkpoint" in desktop
    assert "restore_database_from_point" in desktop
    assert "_lifepilot_pack_privacy_self_test" in desktop


def test_windows_release_keeps_one_click_lifepilot_pilot_available_and_public_safe():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
    desktop = (ROOT / "desktop.py").read_text(encoding="utf-8")
    installer = (ROOT / "packaging" / "installer" / "DocPilot.iss").read_text(encoding="utf-8")

    assert 'if "--pilot" in sys.argv' in desktop
    assert "pilot_main(sys.argv[index + 1 :])" in desktop
    assert "Smoke-test packaged LifePilot Pilot" in workflow
    assert workflow.count("'--pilot'") >= 3
    assert "pilot-public.json" in workflow
    assert "pilot-private.json" in workflow
    assert "created a private report without" in workflow
    assert "LifePilot Pilot.lnk" in workflow
    assert 'Name: "{autoprograms}\\LifePilot Pilot"' in installer
    assert 'Parameters: "--pilot"' in installer
