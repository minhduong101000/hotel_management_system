from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_audit_renderer_uses_safe_dom_states_details_and_busy_feedback():
    script = _source("static/js/audit_log.js")

    assert "renderAuditTableState('loading'" in script
    assert "renderAuditTableState('empty'" in script
    assert "renderAuditTableState('error'" in script
    assert "list.replaceChildren()" in script
    assert "document.createElement('tr')" in script
    assert "document.createElement('details')" in script
    assert "list.innerHTML" not in script
    assert "row.innerHTML" not in script
    assert "let auditLoading = false" in script
    assert "if (auditLoading) return" in script
    assert "setAuditBusy(true)" in script
    assert "setAuditBusy(false)" in script


def test_master_login_toggle_and_submit_feedback_are_presentational_only():
    script = _source("static/js/master_login.js")

    assert "master-password-toggle" in script
    assert "password.type" in script
    assert "aria-pressed" in script
    assert "aria-label" in script
    assert "addEventListener('submit'" in script
    assert "submitButton.disabled = true" in script
    assert "aria-busy" in script
    assert "Đang đăng nhập" in script


def test_master_login_keeps_high_contrast_intro_background():
    styles = _source("static/css/master.css")

    assert re.search(
        r"body\.master-login\s*\{[^}]*background:\s*radial-gradient",
        styles,
        re.DOTALL,
    )
