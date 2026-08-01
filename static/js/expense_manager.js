let warehouseItems = [];
let expenseLoading = false;
let expenseSubmitting = false;
let expenseVoidSubmitting = false;

document.addEventListener('DOMContentLoaded', () => {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('filter-start').value = `${today.substring(0, 8)}01`;
    document.getElementById('filter-end').value = today;
    document.getElementById('exp-date').value = today;
    loadExpenses();
    loadServices();
    loadWarehouseItems();
});

function fmtMoney(value) {
    const amount = Number(value);
    return Number.isFinite(amount) ? new Intl.NumberFormat('vi-VN').format(Math.round(amount)) : '0';
}

function showExpenseFeedback(message, kind = 'success') {
    const feedback = document.getElementById('expense-feedback');
    feedback.textContent = message;
    feedback.className = message ? `alert alert-${kind}` : 'alert d-none';
}

function createExpenseStateIcon(kind) {
    const icons = {loading: 'fas fa-circle-notch fa-spin', empty: 'fas fa-receipt', error: 'fas fa-triangle-exclamation'};
    const wrapper = document.createElement('div');
    wrapper.className = 'data-state__icon';
    const icon = document.createElement('i');
    icon.className = icons[kind] || icons.empty;
    icon.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(icon);
    return wrapper;
}

function renderExpenseTableState(kind, title, description = '', allowRetry = false) {
    const tbody = document.getElementById('expenses-tbody');
    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = 7;
    const state = document.createElement('div');
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    const heading = document.createElement('h3');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.append(createExpenseStateIcon(kind), heading, message);
    if (allowRetry) {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-outline-primary';
        retry.textContent = 'Thử tải lại';
        retry.addEventListener('click', () => loadExpenses());
        actions.appendChild(retry);
        state.appendChild(actions);
    }
    cell.appendChild(state);
    row.appendChild(cell);
    tbody.replaceChildren(row);
}

function setExpenseFilterBusy(isBusy) {
    const button = document.getElementById('expense-filter-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
}

function replaceSelectOptions(select, placeholder, rows, configureOption) {
    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = placeholder;
    const options = [placeholderOption];
    rows.forEach(row => {
        const option = document.createElement('option');
        configureOption(option, row);
        options.push(option);
    });
    select.replaceChildren(...options);
}

function loadServices() {
    return fetch(api('/api/services'))
        .then(response => {
            if (!response.ok) throw new Error('Không thể tải dịch vụ.');
            return response.json();
        })
        .then(services => {
            if (!Array.isArray(services)) throw new Error('Dữ liệu dịch vụ không hợp lệ.');
            replaceSelectOptions(document.getElementById('wh-service'), 'Không liên kết', services, (option, service) => {
                option.value = service.id;
                option.textContent = service.name || `Dịch vụ #${service.id}`;
            });
            replaceSelectOptions(document.getElementById('svc-existing-service'), 'Tạo dịch vụ mới', services, (option, service) => {
                option.value = service.id;
                option.textContent = `${service.name || `Dịch vụ #${service.id}`} (${fmtMoney(service.price)} đ)`;
                option.dataset.name = service.name || '';
                option.dataset.price = Number(service.price || 0);
            });
        })
        .catch(error => showExpenseFeedback(error.message, 'warning'));
}

function loadWarehouseItems() {
    return fetch(api('/api/warehouse'))
        .then(response => {
            if (!response.ok) throw new Error('Không thể tải vật tư kho.');
            return response.json();
        })
        .then(items => {
            if (!Array.isArray(items)) throw new Error('Dữ liệu kho không hợp lệ.');
            warehouseItems = items;
            replaceSelectOptions(document.getElementById('wh-existing-item'), 'Tạo mới / nhập mã tay', items, (option, item) => {
                option.value = item.id;
                option.textContent = `${item.code || '-'} - ${item.name || 'Vật tư'}`;
            });
        })
        .catch(error => showExpenseFeedback(error.message, 'warning'));
}

function applyExistingWarehouseItem() {
    const selectedId = Number(document.getElementById('wh-existing-item').value || 0);
    const item = warehouseItems.find(row => Number(row.id) === selectedId);
    if (!item) return;
    document.getElementById('wh-code').value = item.code || '';
    document.getElementById('wh-name').value = item.name || '';
    document.getElementById('wh-unit').value = item.unit || 'cái';
    document.getElementById('wh-min').value = item.min_quantity ?? 10;
    document.getElementById('wh-service').value = item.service_id || '';
}

function applyExistingService() {
    const select = document.getElementById('svc-existing-service');
    const option = select.options[select.selectedIndex];
    if (!select.value || !option) return;
    document.getElementById('svc-name').value = option.dataset.name || '';
    document.getElementById('svc-price').value = option.dataset.price || '';
    document.getElementById('wh-service').value = select.value;
}

function toggleWarehouseSync() {
    const enabled = document.getElementById('exp-sync-warehouse').checked;
    document.getElementById('warehouse-sync-fields').hidden = !enabled;
    if (!enabled) {
        document.getElementById('exp-sync-service').checked = false;
        document.getElementById('service-sync-fields').hidden = true;
    }
}

function toggleServiceSync() {
    document.getElementById('service-sync-fields').hidden = !document.getElementById('exp-sync-service').checked;
}

function loadExpenses() {
    if (expenseLoading) return;
    const start = document.getElementById('filter-start').value;
    const end = document.getElementById('filter-end').value;
    const category = document.getElementById('filter-category').value;
    if (start && end && end < start) {
        showExpenseFeedback('Đến ngày phải từ ngày bắt đầu trở đi.', 'danger');
        document.getElementById('filter-end').focus();
        return;
    }
    let url = api(`/api/expenses?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
    if (category) url += `&category=${encodeURIComponent(category)}`;
    expenseLoading = true;
    setExpenseFilterBusy(true);
    showExpenseFeedback('');
    renderExpenseTableState('loading', 'Đang tải chi phí', 'Vui lòng chờ trong giây lát.');
    return fetch(url)
        .then(response => response.json().then(data => ({ok: response.ok, data})))
        .then(({ok, data: response}) => {
            if (!ok || !response.success) throw new Error(response.msg || 'Không thể tải chi phí.');
            if (!Array.isArray(response.data)) throw new Error('Dữ liệu chi phí không hợp lệ.');
            document.getElementById('total-amount').textContent = `${fmtMoney(response.total)} đ`;
            renderExpenses(response.data);
        })
        .catch(error => {
            renderExpenseTableState('error', 'Không thể tải chi phí', error.message, true);
            showExpenseFeedback(error.message, 'danger');
        })
        .finally(() => {
            expenseLoading = false;
            setExpenseFilterBusy(false);
        });
}

function createExpenseCell(text, className = '') {
    const cell = document.createElement('td');
    cell.className = className;
    cell.textContent = text ?? '';
    return cell;
}

function createExpenseCategoryBadge(category) {
    const variants = {'Điện nước': 'status-badge--info', 'Lương': 'status-badge--warning', 'Mua sắm': 'status-badge--info', 'Sửa chữa': 'status-badge--neutral', 'Khác': 'status-badge--neutral'};
    const badge = document.createElement('span');
    badge.className = `status-badge ${variants[category] || 'status-badge--neutral'}`;
    badge.textContent = category || 'Khác';
    return badge;
}

function createExpenseVoidButton(expense) {
    const label = `Hủy ghi nhận ${expense.description || `chi phí #${expense.id}`}`;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-icon btn-outline-danger';
    button.setAttribute('aria-label', label);
    button.title = label;
    const icon = document.createElement('i');
    icon.className = 'fas fa-ban';
    icon.setAttribute('aria-hidden', 'true');
    button.appendChild(icon);
    button.addEventListener('click', () => openVoidExpense(expense.id, expense.description));
    return button;
}

function renderExpenses(expenses) {
    if (!expenses.length) {
        renderExpenseTableState('empty', 'Chưa có chi phí', 'Không có khoản chi phù hợp với bộ lọc hiện tại.');
        return;
    }
    const tbody = document.getElementById('expenses-tbody');
    tbody.replaceChildren();
    expenses.forEach(expense => {
        const row = document.createElement('tr');
        const categoryCell = document.createElement('td');
        categoryCell.appendChild(createExpenseCategoryBadge(expense.category));
        const inventoryCell = document.createElement('td');
        if (expense.inventory_code) {
            const code = document.createElement('span');
            code.className = 'status-badge status-badge--info';
            code.textContent = expense.inventory_code;
            const detail = document.createElement('div');
            detail.className = 'small text-muted mt-1';
            detail.textContent = [expense.inventory_name, expense.inventory_service_name].filter(Boolean).join(' → ');
            inventoryCell.append(code, detail);
        } else {
            inventoryCell.className = 'text-muted';
            inventoryCell.textContent = 'Không liên kết';
        }
        const actionCell = document.createElement('td');
        actionCell.className = 'text-end';
        actionCell.appendChild(createExpenseVoidButton(expense));
        row.append(
            createExpenseCell(expense.expense_date || '-', 'numeric-tabular'),
            categoryCell,
            createExpenseCell(expense.description || '-'),
            inventoryCell,
            createExpenseCell(`${fmtMoney(expense.amount)} đ`, 'text-end numeric-tabular fw-bold finance-negative'),
            createExpenseCell(expense.created_by || 'N/A', 'text-muted'),
            actionCell
        );
        tbody.appendChild(row);
    });
}

function clearExpenseFormStatus() {
    const status = document.getElementById('expense-form-status');
    status.textContent = '';
    status.classList.add('d-none');
    document.querySelectorAll('#expenseModal [aria-invalid="true"]').forEach(control => {
        control.removeAttribute('aria-invalid');
        if (control.getAttribute('aria-describedby') === status.id) control.removeAttribute('aria-describedby');
    });
}

function showExpenseFormStatus(message, fieldId) {
    clearExpenseFormStatus();
    const status = document.getElementById('expense-form-status');
    const field = fieldId ? document.getElementById(fieldId) : null;
    status.textContent = message;
    status.classList.remove('d-none');
    if (field) {
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', status.id);
    }
    (field || status).focus();
}

function openAddExpense() {
    clearExpenseFormStatus();
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('exp-category').value = 'Điện nước';
    document.getElementById('exp-desc').value = '';
    document.getElementById('exp-amount').value = '';
    document.getElementById('exp-date').value = today;
    document.getElementById('exp-sync-warehouse').checked = false;
    document.getElementById('warehouse-sync-fields').hidden = true;
    document.getElementById('wh-existing-item').value = '';
    document.getElementById('wh-code').value = '';
    document.getElementById('wh-name').value = '';
    document.getElementById('wh-unit').value = 'cái';
    document.getElementById('wh-qty').value = 1;
    document.getElementById('wh-min').value = 10;
    document.getElementById('wh-service').value = '';
    document.getElementById('exp-sync-service').checked = false;
    document.getElementById('service-sync-fields').hidden = true;
    document.getElementById('svc-existing-service').value = '';
    document.getElementById('svc-name').value = '';
    document.getElementById('svc-price').value = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('expenseModal')).show();
}

function setExpenseSubmitBusy(isBusy) {
    const button = document.getElementById('expense-save-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-save';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang lưu' : 'Lưu chi phí';
    button.replaceChildren(icon, label);
}

function buildExpensePayload() {
    const syncInventory = document.getElementById('exp-sync-warehouse').checked;
    const syncService = document.getElementById('exp-sync-service').checked;
    const payload = {
        category: document.getElementById('exp-category').value,
        description: document.getElementById('exp-desc').value.trim(),
        amount: document.getElementById('exp-amount').value,
        expense_date: document.getElementById('exp-date').value,
        sync_inventory: syncInventory,
        sync_service: syncService,
    };
    if (!payload.description) throw {message: 'Vui lòng nhập mô tả khoản chi.', fieldId: 'exp-desc'};
    if (Number(payload.amount) <= 0) throw {message: 'Số tiền phải lớn hơn 0.', fieldId: 'exp-amount'};
    if (!payload.expense_date) throw {message: 'Vui lòng chọn ngày chi.', fieldId: 'exp-date'};
    if (!syncInventory) return payload;

    const warehouse = {
        code: document.getElementById('wh-code').value.trim(),
        name: document.getElementById('wh-name').value.trim(),
        unit: document.getElementById('wh-unit').value.trim() || 'cái',
        quantity: Number(document.getElementById('wh-qty').value || 0),
        min_quantity: Number(document.getElementById('wh-min').value || 10),
        service_id: document.getElementById('wh-service').value || null,
    };
    if (!warehouse.code) throw {message: 'Vui lòng nhập mã vật tư.', fieldId: 'wh-code'};
    if (!warehouse.name) throw {message: 'Vui lòng nhập tên vật tư.', fieldId: 'wh-name'};
    if (warehouse.quantity <= 0) throw {message: 'Số lượng nhập kho phải lớn hơn 0.', fieldId: 'wh-qty'};
    payload.warehouse = warehouse;
    if (!syncService) return payload;

    const selectedServiceId = document.getElementById('svc-existing-service').value;
    const service = {
        id: selectedServiceId ? Number(selectedServiceId) : null,
        name: document.getElementById('svc-name').value.trim(),
        price: Number(document.getElementById('svc-price').value || 0),
    };
    if (service.id && !warehouse.service_id) warehouse.service_id = service.id;
    if (!service.name && !warehouse.service_id) throw {message: 'Vui lòng nhập tên hoặc chọn dịch vụ để đồng bộ.', fieldId: 'svc-name'};
    if (service.price < 0) throw {message: 'Giá dịch vụ không hợp lệ.', fieldId: 'svc-price'};
    payload.service = service;
    return payload;
}

function saveExpense() {
    if (expenseSubmitting) return;
    let payload;
    try {
        payload = buildExpensePayload();
    } catch (error) {
        showExpenseFormStatus(error.message, error.fieldId);
        return;
    }
    expenseSubmitting = true;
    setExpenseSubmitBusy(true);
    clearExpenseFormStatus();
    return fetch(api('/api/expenses'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    })
        .then(response => response.json().then(data => ({ok: response.ok, data})))
        .then(({ok, data}) => {
            if (!ok || !data.success) throw new Error(data.msg || 'Không thể lưu chi phí.');
            bootstrap.Modal.getOrCreateInstance(document.getElementById('expenseModal')).hide();
            showExpenseFeedback(data.msg || 'Đã lưu chi phí.');
            loadExpenses();
            loadWarehouseItems();
            loadServices();
        })
        .catch(error => showExpenseFormStatus(error.message))
        .finally(() => {
            expenseSubmitting = false;
            setExpenseSubmitBusy(false);
        });
}

function clearExpenseVoidStatus() {
    const status = document.getElementById('void-expense-status');
    status.textContent = '';
    status.classList.add('d-none');
}

function showExpenseVoidStatus(message) {
    const status = document.getElementById('void-expense-status');
    status.textContent = message;
    status.classList.remove('d-none');
    document.getElementById('void-expense-reason').focus();
}

function openVoidExpense(id, description) {
    clearExpenseVoidStatus();
    document.getElementById('void-expense-id').value = id;
    document.getElementById('void-expense-description').textContent = description || `Chi phí #${id}`;
    document.getElementById('void-expense-reason').value = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('voidExpenseModal')).show();
}

function setExpenseVoidBusy(isBusy) {
    const button = document.getElementById('void-expense-submit-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-ban';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang xử lý' : 'Xác nhận hủy';
    button.replaceChildren(icon, label);
}

function confirmVoidExpense() {
    if (expenseVoidSubmitting) return;
    const id = document.getElementById('void-expense-id').value;
    const reason = document.getElementById('void-expense-reason').value.trim();
    if (!reason) {
        showExpenseVoidStatus('Vui lòng nhập lý do hủy ghi nhận.');
        return;
    }
    expenseVoidSubmitting = true;
    setExpenseVoidBusy(true);
    clearExpenseVoidStatus();
    return fetch(api(`/api/expenses/${id}/void`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({reason}),
    })
        .then(response => response.json().then(data => ({ok: response.ok, data})))
        .then(({ok, data}) => {
            if (!ok || !data.success) throw new Error(data.msg || 'Không thể hủy ghi nhận chi phí.');
            bootstrap.Modal.getOrCreateInstance(document.getElementById('voidExpenseModal')).hide();
            showExpenseFeedback(data.msg || 'Đã hủy ghi nhận chi phí.');
            loadExpenses();
        })
        .catch(error => showExpenseVoidStatus(error.message))
        .finally(() => {
            expenseVoidSubmitting = false;
            setExpenseVoidBusy(false);
        });
}
