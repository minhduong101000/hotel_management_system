let allRules = [];
let pricesLoading = false;
const basePriceSubmitting = new Set();
let priceRuleSubmitting = false;

document.addEventListener('DOMContentLoaded', loadData);

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

function createPricingStateRow(kind, title, description, colSpan) {
    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = colSpan;
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
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-outline-primary';
        const icon = document.createElement('i');
        icon.className = 'fas fa-rotate-right';
        icon.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        label.textContent = 'Thử tải lại';
        retry.append(icon, label);
        retry.addEventListener('click', loadData);
        actions.appendChild(retry);
        state.appendChild(actions);
    }

    cell.appendChild(state);
    row.appendChild(cell);
    return row;
}

function renderBaseTableState(kind, title, description = '') {
    const tbody = document.getElementById('base-price-table');
    tbody.replaceChildren(createPricingStateRow(kind, title, description, 4));
}

function renderRulesTableState(kind, title, description = '') {
    const tbody = document.getElementById('rules-table');
    tbody.replaceChildren(createPricingStateRow(kind, title, description, 4));
}

function setPriceRefreshBusy(isBusy) {
    const button = document.getElementById('refresh-prices-button');
    if (!button) return;
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
}

function loadData() {
    if (pricesLoading) return;
    pricesLoading = true;
    setPriceRefreshBusy(true);
    renderBaseTableState('loading', 'Đang tải giá cơ bản', 'Vui lòng chờ trong giây lát.');
    renderRulesTableState('loading', 'Đang tải luật giá', 'Vui lòng chờ trong giây lát.');

    return fetch(api('/api/prices/all-data'))
        .then(response => {
            if (!response.ok) throw new Error('Không thể tải dữ liệu giá phòng.');
            return response.json();
        })
        .then(data => {
            if (data.error) throw new Error(data.error);
            if (!Array.isArray(data.rooms) || !Array.isArray(data.rules)) {
                throw new Error('Dữ liệu giá phòng không hợp lệ.');
            }
            allRules = data.rules;
            renderBaseTable(data.rooms);
            renderRulesTable(data.rules);
        })
        .catch(error => {
            renderBaseTableState('error', 'Không thể tải giá cơ bản', error.message);
            renderRulesTableState('error', 'Không thể tải luật giá', error.message);
        })
        .finally(() => {
            pricesLoading = false;
            setPriceRefreshBusy(false);
        });
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

function createPriceInput(id, value, label, options = {}) {
    const group = document.createElement('div');
    group.className = 'input-group input-group-sm pricing-input-group';
    const hiddenLabel = document.createElement('label');
    hiddenLabel.className = 'visually-hidden';
    hiddenLabel.htmlFor = id;
    hiddenLabel.textContent = label;

    if (options.prefix) {
        const prefix = document.createElement('span');
        prefix.className = 'input-group-text pricing-input-label';
        prefix.textContent = options.prefix;
        group.appendChild(prefix);
    }

    const input = document.createElement('input');
    input.type = 'number';
    input.className = `form-control numeric-tabular${options.emphasis ? ' fw-bold' : ''}`;
    input.id = id;
    input.value = Number(value) || 0;
    input.step = options.step || '1000';
    input.min = '0';
    input.inputMode = 'numeric';
    group.append(hiddenLabel, input);

    if (options.suffix) {
        const suffix = document.createElement('span');
        suffix.className = 'input-group-text';
        suffix.textContent = options.suffix;
        group.appendChild(suffix);
    }
    return group;
}

function renderBaseTable(rooms) {
    if (!rooms.length) {
        renderBaseTableState('empty', 'Chưa có phòng để thiết lập giá', 'Phòng mới sẽ xuất hiện tại đây sau khi được cấu hình.');
        return;
    }

    const tbody = document.getElementById('base-price-table');
    tbody.replaceChildren();
    rooms.forEach(room => {
        const row = document.createElement('tr');

        const roomCell = document.createElement('td');
        roomCell.className = 'ps-3 pricing-room-cell';
        const roomNumber = document.createElement('strong');
        roomNumber.className = 'pricing-room-number';
        roomNumber.textContent = `P.${room.number}`;
        roomCell.append(roomNumber, createPriceBadge(room.type || 'Chưa phân loại'));

        const dailyCell = document.createElement('td');
        dailyCell.appendChild(createPriceInput(
            `base-d-${room.id}`,
            room.price_daily,
            `Giá ngày phòng ${room.number}`,
            {step: '10000', suffix: 'đ', emphasis: true}
        ));

        const hourlyCell = document.createElement('td');
        const hourlyStack = document.createElement('div');
        hourlyStack.className = 'pricing-hourly-stack';
        hourlyStack.append(
            createPriceInput(`base-init-${room.id}`, room.price_initial, `Giá block đầu phòng ${room.number}`, {prefix: 'Đầu'}),
            createPriceInput(`base-next-${room.id}`, room.price_next, `Giá giờ tiếp theo phòng ${room.number}`, {prefix: 'Tiếp'})
        );
        hourlyCell.appendChild(hourlyStack);

        const actionCell = document.createElement('td');
        actionCell.className = 'text-end pe-3';
        const save = createPriceActionButton(`Lưu giá phòng ${room.number}`, 'fas fa-save', 'btn-outline-primary', () => updateBase(room.id));
        save.id = `base-save-${room.id}`;
        save.setAttribute('aria-busy', 'false');
        actionCell.appendChild(save);
        row.append(roomCell, dailyCell, hourlyCell, actionCell);
        tbody.appendChild(row);
    });
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
        renderRulesTableState('empty', 'Chưa có luật giá', 'Giá cơ bản đang được áp dụng cho mọi thời điểm.');
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
        if (Number(rule.priority) === 2) {
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
            createPriceActionButton(`Sửa ${ruleName}`, 'fas fa-pen', 'btn-outline-primary', () => editRule(rule.id)),
            createPriceActionButton(`Xóa ${ruleName}`, 'fas fa-trash', 'btn-outline-danger', () => deleteRule(rule.id))
        );
        actionCell.appendChild(actions);
        row.append(eventCell, timeCell, priceCell, actionCell);
        tbody.appendChild(row);
    });
}

function showPriceFeedback(message, kind = 'success') {
    const feedback = document.getElementById('price-feedback');
    feedback.className = `alert alert-${kind}`;
    feedback.textContent = message;
}

function setBasePriceBusy(id, isBusy) {
    const button = document.getElementById(`base-save-${id}`);
    if (!button) return;
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-save';
    icon.setAttribute('aria-hidden', 'true');
    button.replaceChildren(icon);
}

function updateBase(id) {
    if (basePriceSubmitting.has(id)) return;
    const daily = document.getElementById(`base-d-${id}`).value;
    const initial = document.getElementById(`base-init-${id}`).value;
    const next = document.getElementById(`base-next-${id}`).value;
    basePriceSubmitting.add(id);
    setBasePriceBusy(id, true);

    return fetch(api('/api/prices/update-base'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id, price_daily: daily, price_initial: initial, price_next: next}),
    })
        .then(response => {
            if (!response.ok) throw new Error('Không thể cập nhật giá phòng.');
            return response.json();
        })
        .then(data => {
            if (!data.success) throw new Error(data.msg || 'Không thể cập nhật giá phòng.');
            showPriceFeedback(data.msg || 'Đã cập nhật giá phòng.');
        })
        .catch(error => showPriceFeedback(error.message, 'danger'))
        .finally(() => {
            basePriceSubmitting.delete(id);
            setBasePriceBusy(id, false);
        });
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
    const titleText = document.getElementById('rule-modal-title-text');
    const titleIcon = document.querySelector('#ruleModalTitle i');
    titleText.textContent = label;
    titleIcon.className = `${iconClass} me-2`;
}

function openRuleModal() {
    document.getElementById('r-id').value = '';
    document.getElementById('rule-form').reset();
    document.querySelectorAll('input[name="daycheck"]').forEach(checkbox => { checkbox.checked = true; });
    clearRuleFormStatus();
    setRuleModalTitle('Thêm luật giá', 'fas fa-plus');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).show();
}

function editRule(id) {
    const rule = allRules.find(item => item.id === id);
    if (!rule) return;
    document.getElementById('r-id').value = rule.id;
    document.getElementById('r-name').value = rule.name;
    document.getElementById('r-room-type').value = rule.room_type;
    document.getElementById('r-priority').value = rule.priority;
    document.getElementById('r-start').value = rule.start_date || '';
    document.getElementById('r-end').value = rule.end_date || '';
    document.getElementById('r-price-daily').value = rule.price_daily;
    document.querySelectorAll('input[name="daycheck"]').forEach(checkbox => { checkbox.checked = false; });
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

function saveRule() {
    if (priceRuleSubmitting) return;
    const days = Array.from(document.querySelectorAll('input[name="daycheck"]:checked')).map(checkbox => checkbox.value);
    const payload = {
        id: document.getElementById('r-id').value,
        name: document.getElementById('r-name').value.trim(),
        room_type: document.getElementById('r-room-type').value,
        priority: document.getElementById('r-priority').value,
        start_date: document.getElementById('r-start').value,
        end_date: document.getElementById('r-end').value,
        days_of_week: days,
        price_daily: document.getElementById('r-price-daily').value,
    };

    if (!payload.name) {
        showRuleFormStatus('Vui lòng nhập tên sự kiện.', 'r-name');
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
    return fetch(api('/api/prices/save-rule'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    })
        .then(response => response.json().then(data => ({ok: response.ok, data})))
        .then(({ok, data}) => {
            if (!ok || !data.success) throw new Error(data.msg || 'Không thể lưu luật giá.');
            bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).hide();
            showPriceFeedback(data.msg || 'Đã lưu luật giá.');
            loadData();
        })
        .catch(error => showRuleFormStatus(error.message))
        .finally(() => {
            priceRuleSubmitting = false;
            setRuleSubmitBusy(false);
        });
}

function deleteRule(id) {
    if (!confirm('Xóa luật giá này?')) return;
    fetch(api(`/api/prices/delete-rule/${id}`), {method: 'DELETE'})
        .then(response => {
            if (!response.ok) throw new Error('Không thể xóa luật giá.');
            return response.json();
        })
        .then(data => {
            showPriceFeedback(data.msg, data.success ? 'success' : 'danger');
            if (data.success) loadData();
        })
        .catch(error => showPriceFeedback(error.message, 'danger'));
}

function formatCurrency(amount) {
    const value = Number(amount);
    return Number.isFinite(value) ? new Intl.NumberFormat('vi-VN').format(value) : '0';
}
