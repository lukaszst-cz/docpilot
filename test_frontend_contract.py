from pathlib import Path
import re


ROOT = Path(__file__).parent


def test_dynamic_collections_use_query_selector_all():
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    bad = re.findall(r"(?<!\$)\$\([^\n;]+\)\.forEach", script)
    assert bad == []
    assert "$$('.duplicateOpen').forEach" in script
    assert "$$('.docSelect').forEach" in script
    assert "$$('.ruleEdit').forEach" in script
    assert "$$('.navBtn').forEach" in script
    assert "const items=$$('.navBtn');" in script


def test_core_navigation_exposes_accessibility_hooks():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'class="skipLink"' in html
    assert 'id="mainContent" tabindex="-1"' in html
    assert 'id="viewTitle" tabindex="-1"' in html
    assert 'aria-current="page"' in html
    assert 'aria-label="Search local documents"' in html
    assert 'aria-label="Ask a question about local documents"' in html
    assert "b.setAttribute('aria-current','page')" in script
    assert "$('#nav')?.addEventListener('keydown'" in script


def test_frontend_uses_in_app_notices_instead_of_alerts():
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "alert(" not in script
    assert "showAppNotice(" in script


def test_long_paths_and_narrow_layout_have_css_guards():
    css = (ROOT / "app.css").read_text(encoding="utf-8")
    assert "overflow-wrap:anywhere" in css
    assert "word-break:break-word" in css
    assert "@media(max-width:800px)" in css
    assert ".appShell{grid-template-columns:1fr}" in css


def test_original_file_changes_require_user_confirmation():
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert "if(current.source_mode==='original')" in script
    assert "const ok=confirm(" in script
    assert "if(!ok)return;" in script
    assert "Undo History" in script
    assert "mode==='rename'?'rename the original file':'move the original file into the DocPilot archive'" in script


def test_rules_ui_supports_edit_pause_and_delete():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="ruleDocType"' in html
    assert 'id="ruleTags"' in html
    assert 'id="cancelRuleEditBtn"' in html
    assert "ruleEdit" in script
    assert "ruleToggle" in script
    assert "ruleDelete" in script
    assert "editingRuleId" in script
    assert "Save changes" in script
    assert "method:'PATCH'" in script
    assert "method:'DELETE'" in script


def test_documents_ui_exposes_bulk_case_profile_and_action_controls():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="bulkDocumentsBar"' in html
    assert 'id="bulkCaseMode"' in html
    assert 'id="bulkProfile"' in html
    assert 'id="bulkAction"' in html
    assert 'id="applyBulkDocs"' in html
    assert 'id="selectAllDocs"' in script
    assert 'class="docSelect"' in script
    assert "/api/documents/batch-update" in script
    assert "selectedDocumentIds" in script


def test_cases_ui_exposes_summary_and_openable_timeline():
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert "c.document_count" in script
    assert "c.open_actions" in script
    assert "c.next_deadline" in script
    assert "c.overdue_deadlines" in script
    assert "caseTimelineRow" in script
    assert "caseOpen" in script


def test_documents_ui_uses_lightweight_pagination_controls():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="documentsFilter"' in html
    assert 'id="prevDocumentsPage"' in html
    assert 'id="nextDocumentsPage"' in html
    assert 'id="documentsPageInfo"' in html
    assert "/api/documents/page?" in script
    assert "documentsPageLimit = 100" in script
    assert "documentsPageOffset" in script


def test_profiles_explain_physical_archive_spaces():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert "archive/Profiles/&lt;profile&gt;" in html
    assert "Changing profile metadata later does not move an already archived file." in html


def test_settings_exposes_integration_scope_and_history():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="integrationPreviewProvider"' in html
    assert 'id="integrationScopeProfile"' in html
    assert 'id="integrationScopeCase"' in html
    assert 'id="integrationScopeAction"' in html
    assert 'id="integrationScopeCategory"' in html
    assert 'id="integrationScopeLimit"' in html
    assert 'id="integrationHistory"' in html
    assert "/api/integrations/preview" in script
    assert "/api/integrations/history?limit=20" in script
    assert "integrationScope()" in script


def test_ui_exposes_portable_config_export_preview_and_apply():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'href="/api/export/config"' in html
    assert 'id="configImportFile"' in html
    assert 'id="configPreviewBtn"' in html
    assert 'id="configApplyBtn"' in html
    assert 'id="configImportPreview"' in html
    assert "/api/config/preview" in script
    assert "/api/config/import" in script
    assert "pendingPortableConfig" in script
    assert "Credentials and machine-specific paths will not be imported." in script


def test_integration_preview_options_come_from_adapter_catalog():
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert "/api/integrations/catalog" in script
    assert "item.supports_scope&&item.supports_document_sync" in script
    assert "integrationPreviewProvider" in script


def test_settings_exposes_recovery_checkpoint_controls():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="recoveryCheckpointBtn"' in html
    assert 'id="recoveryRefreshBtn"' in html
    assert 'id="recoveryList"' in html
    assert "/api/recovery/checkpoint" in script
    assert "loadRecoveryPoints" in script
    assert "database_integrity" in script
    assert "supported_schema_version" in script


def test_recovery_restore_requires_typed_confirmation_in_ui():
    script = (ROOT / "app.js").read_text(encoding="utf-8")

    assert "recoveryRestore" in script
    assert "Type RESTORE to continue." in script
    assert "if(typed!=='RESTORE')return;" in script
    assert "/api/recovery/restore" in script
    assert "confirm:'RESTORE'" in script
