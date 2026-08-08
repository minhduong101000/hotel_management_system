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
    rules_script = _source("static/js/price_manager.js")
    room_script = _source("static/js/room_settings.js")

    # price_manager.js now only renders rules (base-price moved to room_settings.js)
    assert "function renderRulesTableState(" in rules_script
    assert "renderRulesTableState('loading'" in rules_script
    assert "Chưa có luật giá" in rules_script  # empty state title
    assert "Không thể tải luật giá" in rules_script  # error state title
    assert "tbody.replaceChildren()" in rules_script
    assert "document.createElement('tr')" in rules_script
    assert "tr.innerHTML" not in rules_script
    assert "tbody.innerHTML" not in rules_script
    assert "button.className = `btn btn-icon" in rules_script
    assert "button.setAttribute('aria-label', label)" in rules_script
    assert "button.title = label" in rules_script

    # room_settings.js handles room table with structured states
    assert "function renderRoomSettingsState(" in room_script
    assert "renderRoomSettingsState('loading'" in room_script
    assert "Chưa có phòng phù hợp" in room_script  # empty state title
    assert "Không thể tải cấu hình phòng" in room_script  # error state title
    assert "tbody.replaceChildren()" in room_script
    assert "document.createElement('tr')" in room_script
    assert "button.className = `btn btn-icon" in room_script
    assert "button.setAttribute('aria-label', label)" in room_script
    assert "button.title = label" in room_script


def test_price_updates_and_rule_save_expose_busy_feedback():
    rules_script = _source("static/js/price_manager.js")
    room_script = _source("static/js/room_settings.js")

    # Rule busy state in price_manager.js
    assert "let priceRuleSubmitting = false" in rules_script
    assert "if (priceRuleSubmitting) return" in rules_script
    assert "setRuleSubmitBusy(true)" in rules_script
    assert "setRuleSubmitBusy(false)" in rules_script
    assert "showRuleFormStatus" in rules_script
    assert "} finally {" in rules_script

    # Room settings and rate busy state in room_settings.js
    assert "let roomSettingsSubmitting = false" in room_script
    assert "if (roomSettingsSubmitting) return" in room_script
    assert "setRoomSettingsSubmitBusy(true)" in room_script
    assert "setRoomSettingsSubmitBusy(false)" in room_script
    assert "let roomRateSubmitting = false" in room_script
    assert "if (roomRateSubmitting) return" in room_script
    assert "setRoomRateSubmitBusy(true)" in room_script
    assert "setRoomRateSubmitBusy(false)" in room_script
    assert "} finally {" in room_script
