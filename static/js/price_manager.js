let allRules = [];
let priceRuleRoomTypes = [];
let pricesLoading = false;
let priceRuleSubmitting = false;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refresh-prices-button')?.addEventListener('click', loadData);
    document.getElementById('add-price-rule-button')?.addEventListener('click', openRuleModal);
    document.getElementById('rule-form')?.addEventListener('submit', saveRule);
    loadData();
});

function createPricingStateIcon(kind) {
    const icons = {
        loading: 'fas fa-circle-notch fa-spin',
        empty: 'fas fa-tags',
        error: 'fas fa-triangle-exclamation',
    };
    const wrapper = document.createElement('div');
    wrapper.className = 'data-state__icon';
    const icon = document.createElement('i');
    icon.className = icons[kind] || icons.empty;
    icon.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(icon);
    return wrapper;
}

function createPricingStateRow(kind, title, description) {
    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = 4;
    const state = document.createElement('div');
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    const heading = document.createElement('h3');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.append(createPricingStateIcon(kind), heading, message);

    if (kind === 'error') {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        const retry = createPriceActionButton(
            'Thử tải lại luật giá',
            'fas fa-rotate-right',
            'btn-outline-primary',
            loadData
        );
        const label = document.createElement('span');
        label.textContent = 'Thử tải lại';
        retry.appendChild(label);
        actions.appendChild(retry);
        state.appendChild(actions);
    }

    cell.appendChild(state);
    row.appendChild(cell);
    return row;
}

function renderRulesTableState(kind, title, description = '') {
    document.getElementById('rules-table').replaceChildren(
        createPricingStateRow(kind, title, description)
    );
}

function setPriceRefreshBusy(isBusy) {
    const button = document.getElementById('refresh-prices-button');
    if (!button) return;
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
}

async function loadData() {
    if (pricesLoading) return;
    pricesLoading = true;
    setPriceRefreshBusy(true);
    renderRulesTableState('loading', 'Đang tải luật giá', 'Vui lòng chờ trong giây lát.');
    try {
        const data = await requestPriceJson(api('/api/prices/rules'));
        if (!Array.isArray(data.rules) || !Array.isArray(data.room_types)) {
            throw new Error('Dữ liệu luật giá không hợp lệ.');
        }
        allRules = data.rules;
        priceRuleRoomTypes = data.room_types;
        renderRoomTypeOptions();
        renderRulesTable(allRules);
    } catch (error) {
        renderRulesTableState(
            'error',
            'Không thể tải luật giá',
            priceErrorMessage(error)
        );
    } finally {
        pricesLoading = false;
        setPriceRefreshBusy(false);
    }
}

function createPriceActionButton(label, iconClass, variant, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `btn btn-icon ${variant}`;
    button.setAttribute('aria-label', label);
    button.title = label;
    const icon = document.createElement('i');
    icon.className = iconClass;
    icon.setAttribute('aria-hidden', 'true');
    button.appendChild(icon);
    button.addEventListener('click', handler);
    return button;
}

function createPriceBadge(text, className = 'status-badge--neutral') {
    const badge = document.createElement('span');
    badge.className = `status-badge ${className}`;
    badge.textContent = text;
    return badge;
}

function createRuleTimeContent(rule) {
    const wrapper = document.createElement('div');
    if (rule.start_date) {
        const range = document.createElement('strong');
        range.className = 'pricing-rule-range numeric-tabular';
        range.textContent = `${rule.start_date} → ${rule.end_date || rule.start_date}`;
        wrapper.appendChild(range);
    } else {
        wrapper.appendChild(createPriceBadge('Cả năm'));
    }

    const days = document.createElement('div');
    days.className = 'pricing-rule-days';
    if (rule.days_of_week) {
        const dayNames = {'0': 'T2', '1': 'T3', '2': 'T4', '3': 'T5', '4': 'T6', '5': 'T7', '6': 'CN'};
        rule.days_of_week.split(',').forEach(day => {
            if (!dayNames[day]) return;
            const badge = document.createElement('span');
            badge.className = `pricing-day-badge${day === '5' || day === '6' ? ' pricing-day-badge--weekend' : ''}`;
            badge.textContent = dayNames[day];
            days.appendChild(badge);
        });
    } else {
        days.textContent = 'Tất cả các ngày';
    }
    wrapper.appendChild(days);
    return wrapper;
}

function renderRulesTable(rules) {
    if (!rules.length) {
        renderRulesTableState(
            'empty',
            'Chưa có luật giá',
            'Giá mặc định của từng phòng đang được áp dụng.'
        );
        return;
    }

    const tbody = document.getElementById('rules-table');
    tbody.replaceChildren();
    rules.forEach(rule => {
        const row = document.createElement('tr');
        const eventCell = document.createElement('td');
        eventCell.className = 'ps-3';
        const nameLine = document.createElement('div');
        nameLine.className = 'pricing-rule-name';
        const name = document.createElement('strong');
        name.textContent = rule.name || '-';
        nameLine.appendChild(name);
        if (!rule.is_active) {
            nameLine.appendChild(createPriceBadge('Tạm ngưng', 'status-badge--neutral'));
        } else if (Number(rule.priority) > 1) {
            nameLine.appendChild(createPriceBadge('Ưu tiên cao', 'status-badge--warning'));
        }
        eventCell.append(nameLine, createPriceBadge(rule.room_type || 'Mọi loại phòng'));

        const timeCell = document.createElement('td');
        timeCell.appendChild(createRuleTimeContent(rule));

        const priceCell = document.createElement('td');
        priceCell.className = 'text-end numeric-tabular fw-bold pricing-rule-price';
        priceCell.textContent = `${formatCurrency(rule.price_daily)} đ`;

        const actionCell = document.createElement('td');
        actionCell.className = 'text-end pe-3';
        const actions = document.createElement('div');
        actions.className = 'table-row-actions button-group';
        const ruleName = rule.name || 'luật giá';
        actions.append(
            createPriceActionButton(
                `Sửa ${ruleName}`,
                'fas fa-pen',
                'btn-outline-primary',
                () => editRule(rule.id)
            ),
            createPriceActionButton(
                `Xóa ${ruleName}`,
                'fas fa-trash',
                'btn-outline-danger',
                () => deleteRule(rule.id)
            )
        );
        actionCell.appendChild(actions);
        row.append(eventCell, timeCell, priceCell, actionCell);
        tbody.appendChild(row);
    });
}

function renderRoomTypeOptions(selectedValue = '') {
    const select = document.getElementById('r-room-type');
    const currentValue = selectedValue || select.value;
    select.replaceChildren();
    priceRuleRoomTypes.forEach(roomType => {
        const option = document.createElement('option');
        option.value = roomType;
        option.textContent = roomType;
        select.appendChild(option);
    });
    if (priceRuleRoomTypes.includes(currentValue)) {
        select.value = currentValue;
    }
}

function showPriceFeedback(message, kind = 'success') {
    const feedback = document.getElementById('price-feedback');
    feedback.className = `alert alert-${kind}`;
    feedback.textContent = message;
}

function clearRuleFormStatus() {
    const status = document.getElementById('rule-form-status');
    status.textContent = '';
    status.classList.add('d-none');
    document.querySelectorAll('#ruleModal [aria-invalid="true"]').forEach(control => {
        control.removeAttribute('aria-invalid');
        if (control.getAttribute('aria-describedby') === status.id) {
            control.removeAttribute('aria-describedby');
        }
    });
}

function showRuleFormStatus(message, fieldId) {
    clearRuleFormStatus();
    const status = document.getElementById('rule-form-status');
    const field = fieldId ? document.getElementById(fieldId) : null;
    status.textContent = message;
    status.classList.remove('d-none');
    if (field) {
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', status.id);
        field.focus();
    } else {
        status.focus();
    }
}

function setRuleModalTitle(label, iconClass) {
    document.getElementById('rule-modal-title-text').textContent = label;
    document.querySelector('#ruleModalTitle i').className = `${iconClass} me-2`;
}

function openRuleModal() {
    document.getElementById('rule-form').reset();
    document.getElementById('r-id').value = '';
    renderRoomTypeOptions();
    document.querySelectorAll('input[name="daycheck"]').forEach(checkbox => {
        checkbox.checked = true;
    });
    clearRuleFormStatus();
    setRuleModalTitle('Thêm luật giá', 'fas fa-plus');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).show();
}

function editRule(id) {
    const rule = allRules.find(item => item.id === id);
    if (!rule) return;
    document.getElementById('r-id').value = rule.id;
    document.getElementById('r-name').value = rule.name;
    renderRoomTypeOptions(rule.room_type);
    document.getElementById('r-priority').value = rule.priority;
    document.getElementById('r-start').value = rule.start_date || '';
    document.getElementById('r-end').value = rule.end_date || '';
    document.getElementById('r-price-daily').value = rule.price_daily;
    document.querySelectorAll('input[name="daycheck"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    if (rule.days_of_week) {
        const selectedDays = rule.days_of_week.split(',');
        document.querySelectorAll('input[name="daycheck"]').forEach(checkbox => {
            checkbox.checked = selectedDays.includes(checkbox.value);
        });
    }
    clearRuleFormStatus();
    setRuleModalTitle(`Cập nhật: ${rule.name}`, 'fas fa-pen');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).show();
}

function setRuleSubmitBusy(isBusy) {
    const button = document.getElementById('rule-save-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-save';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang lưu' : 'Lưu luật giá';
    button.replaceChildren(icon, label);
}

async function saveRule(event) {
    event.preventDefault();
    if (priceRuleSubmitting) return;
    const payload = {
        id: document.getElementById('r-id').value,
        name: document.getElementById('r-name').value.trim(),
        room_type: document.getElementById('r-room-type').value,
        priority: document.getElementById('r-priority').value,
        start_date: document.getElementById('r-start').value,
        end_date: document.getElementById('r-end').value,
        days_of_week: Array.from(
            document.querySelectorAll('input[name="daycheck"]:checked')
        ).map(checkbox => checkbox.value),
        price_daily: document.getElementById('r-price-daily').value,
    };
    if (!payload.name) {
        showRuleFormStatus('Vui lòng nhập tên sự kiện.', 'r-name');
        return;
    }
    if (!payload.room_type) {
        showRuleFormStatus('Hãy chọn loại phòng.', 'r-room-type');
        return;
    }
    if (payload.start_date && payload.end_date && payload.end_date < payload.start_date) {
        showRuleFormStatus('Ngày kết thúc phải từ ngày bắt đầu trở đi.', 'r-end');
        return;
    }
    if (Number(payload.price_daily) <= 0) {
        showRuleFormStatus('Giá qua đêm phải lớn hơn 0.', 'r-price-daily');
        return;
    }

    priceRuleSubmitting = true;
    setRuleSubmitBusy(true);
    clearRuleFormStatus();
    try {
        const data = await requestPriceJson(api('/api/prices/save-rule'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).hide();
        showPriceFeedback(data.msg || 'Đã lưu luật giá.');
        await loadData();
    } catch (error) {
        showRuleFormStatus(priceErrorMessage(error));
    } finally {
        priceRuleSubmitting = false;
        setRuleSubmitBusy(false);
    }
}

async function deleteRule(id) {
    const rule = allRules.find(item => item.id === id);
    const name = rule?.name || 'luật giá này';
    if (!window.confirm(`Xóa ${name}?`)) return;
    try {
        const data = await requestPriceJson(
            api(`/api/prices/delete-rule/${id}`),
            {method: 'DELETE'}
        );
        showPriceFeedback(data.msg || 'Đã xóa luật giá.');
        await loadData();
    } catch (error) {
        showPriceFeedback(priceErrorMessage(error), 'danger');
    }
}

async function requestPriceJson(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};
    try {
        data = await response.json();
    } catch (_error) {
        data = {};
    }
    if (!response.ok || data.success === false) {
        const error = new Error(data.msg || 'Không thể hoàn tất thao tác.');
        error.status = response.status;
        error.data = data;
        throw error;
    }
    return data;
}

function priceErrorMessage(error) {
    if (error.status === 400) return error.message || 'Dữ liệu chưa hợp lệ.';
    if (error.status === 403) return 'Bạn không có quyền thực hiện thao tác này.';
    if (error.status === 404) return 'Không tìm thấy luật giá.';
    if (error instanceof TypeError) return 'Không thể kết nối máy chủ. Vui lòng thử lại.';
    return error.message || 'Không thể hoàn tất thao tác.';
}

function formatCurrency(amount) {
    const value = Number(amount);
    return Number.isFinite(value)
        ? new Intl.NumberFormat('vi-VN').format(value)
        : '0';
}
