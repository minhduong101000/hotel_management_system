from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_service_renderer_uses_safe_dom_actions_and_structured_states():
    script = _source("static/js/service_manager.js")

    assert "renderServiceTableState('loading'" in script
    assert "renderServiceTableState('empty'" in script
    assert "renderServiceTableState('error'" in script
    assert "tbody.replaceChildren()" in script
    assert "document.createElement('tr')" in script
    assert ".textContent = service.name" in script
    assert "tr.innerHTML" not in script
    assert "tbody.innerHTML" not in script
    assert "button.className = `btn btn-icon" in script
    assert "button.setAttribute('aria-label', label)" in script
    assert "button.title = label" in script
    assert "action.addEventListener('click', () => openModal())" in script


def test_service_save_has_status_feedback_and_double_submit_guard():
    script = _source("static/js/service_manager.js")

    assert "let serviceSubmitting = false" in script
    assert "if (serviceSubmitting) return" in script
    assert "setServiceSubmitBusy(true)" in script
    assert "setServiceSubmitBusy(false)" in script
    assert ".finally(" in script
    assert "showServiceFormStatus" in script
    assert "alert(" not in script


def test_price_renderers_use_safe_dom_actions_and_structured_states():
    script = _source("static/js/price_manager.js")

    for state_function in (
        "renderBaseTableState",
        "renderRulesTableState",
    ):
        assert f"{state_function}('loading'" in script
        assert f"{state_function}('empty'" in script
        assert f"{state_function}('error'" in script
    assert script.count("tbody.replaceChildren()") >= 2
    assert "document.createElement('tr')" in script
    assert "tr.innerHTML" not in script
    assert "tbody.innerHTML" not in script
    assert "button.className = `btn btn-icon" in script
    assert "button.setAttribute('aria-label', label)" in script
    assert "button.title = label" in script
    assert "titleText.textContent" in script


def test_price_updates_and_rule_save_expose_busy_feedback():
    script = _source("static/js/price_manager.js")

    assert "const basePriceSubmitting = new Set()" in script
    assert "if (basePriceSubmitting.has(id)) return" in script
    assert "setBasePriceBusy(id, true)" in script
    assert "setBasePriceBusy(id, false)" in script
    assert "let priceRuleSubmitting = false" in script
    assert "if (priceRuleSubmitting) return" in script
    assert "setRuleSubmitBusy(true)" in script
    assert "setRuleSubmitBusy(false)" in script
    assert "showRuleFormStatus" in script
    assert ".finally(" in script
