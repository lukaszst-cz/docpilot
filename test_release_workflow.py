from pathlib import Path


ROOT = Path(__file__).parent


def test_windows_release_only_auto_publishes_stable_main_builds():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")

    assert "Resolve stable release version" in workflow
    assert "re.fullmatch(r\'[0-9]+\\.[0-9]+\\.[0-9]+\'" in workflow
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
