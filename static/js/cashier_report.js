let cashierLoading = false;

document.addEventListener('DOMContentLoaded', () => {
    bindCashierFilters();
    loadCashierData();
});

function bindCashierFilters() {
    const customSwitch = document.getElementById('custom-date-switch');
    const customGroup = document.getElementById('custom-date-group');
    customSwitch.addEventListener('change', event => {
        customGroup.hidden = !event.target.checked;
        if (event.target.checked) {
            document.querySelectorAll('input[name="period"]').forEach(radio => { radio.checked = false; });
        } else {
            document.getElementById('btn-today').checked = true;
        }
        clearCashierFilterStatus();
    });
    document.querySelectorAll('input[name="period"]').forEach(radio => {
        radio.addEventListener('change', () => {
            customSwitch.checked = false;
            customGroup.hidden = true;
            clearCashierFilterStatus();
        });
    });
}

function fmtMoney(value) {
    const amount = Number(value);
    return Number.isFinite(amount) ? new Intl.NumberFormat('vi-VN').format(Math.round(amount)) : '0';
}

function createCashierStateIcon(kind) {
    const icons = {loading: 'fas fa-circle-notch fa-spin', empty: 'fas fa-receipt', error: 'fas fa-triangle-exclamation'};
    const wrapper = document.createElement('div');
    wrapper.className = 'data-state__icon';
    const icon = document.createElement('i');
    icon.className = icons[kind] || icons.empty;
    icon.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(icon);
    return wrapper;
}

function renderCashierTableState(kind, title, description = '', allowRetry = false) {
    const tbody = document.getElementById('payment-table-body');
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
    state.append(createCashierStateIcon(kind), heading, message);
    if (allowRetry) {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-outline-primary';
        retry.textContent = 'Thử tải lại';
        retry.addEventListener('click', () => loadCashierData());
        actions.appendChild(retry);
        state.appendChild(actions);
    }
    cell.appendChild(state);
    row.appendChild(cell);
    tbody.replaceChildren(row);
}

function clearCashierFilterStatus() {
    const status = document.getElementById('cashier-filter-status');
    status.textContent = '';
    status.classList.add('d-none');
}

function showCashierFilterStatus(message, fieldId) {
    clearCashierFilterStatus();
    const status = document.getElementById('cashier-filter-status');
    status.textContent = message;
    status.classList.remove('d-none');
    const field = fieldId ? document.getElementById(fieldId) : null;
    (field || status).focus();
}

function clearDepositPrintStatus() {
    const status = document.getElementById('deposit-print-status');
    status.textContent = '';
    status.classList.add('d-none');
}

function showDepositPrintStatus(message) {
    const status = document.getElementById('deposit-print-status');
    status.textContent = message;
    status.classList.remove('d-none');
    document.getElementById('deposit-booking-id').focus();
}

function setCashierLoadBusy(isBusy) {
    const button = document.getElementById('cashier-load-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-rotate-right';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang tải' : 'Tải dữ liệu';
    button.replaceChildren(icon, label);
}

function buildCashierUrl() {
    const isCustom = document.getElementById('custom-date-switch').checked;
    const selectedPeriod = document.querySelector('input[name="period"]:checked');
    const period = isCustom ? 'custom' : (selectedPeriod ? selectedPeriod.value : 'today');
    let url = api(`/api/reports/cashier?period=${period}`);
    if (!isCustom) return url;
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) throw new Error('Vui lòng chọn đầy đủ từ ngày và đến ngày.');
    if (end < start) throw new Error('Đến ngày phải từ ngày bắt đầu trở đi.');
    return `${url}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
}

function loadCashierData() {
    if (cashierLoading) return;
    let url;
    try {
        url = buildCashierUrl();
    } catch (error) {
        showCashierFilterStatus(error.message, 'start-date');
        return;
    }
    cashierLoading = true;
    setCashierLoadBusy(true);
    clearCashierFilterStatus();
    renderCashierTableState('loading', 'Đang tải giao dịch', 'Vui lòng chờ trong giây lát.');
    return fetch(url)
        .then(response => response.json().then(data => ({ok: response.ok, data})))
        .then(({ok, data: response}) => {
            if (!ok || !response.success) throw new Error(response.msg || 'Không thể tải sổ quỹ.');
            if (!response.data || !Array.isArray(response.data.records)) throw new Error('Dữ liệu sổ quỹ không hợp lệ.');
            renderCashierOverview(response.data);
            renderCashierTable(response.data.records);
        })
        .catch(error => {
            renderCashierTableState('error', 'Không thể tải giao dịch', error.message, true);
            showCashierFilterStatus(error.message);
        })
        .finally(() => {
            cashierLoading = false;
            setCashierLoadBusy(false);
        });
}

function renderCashierOverview(data) {
    document.getElementById('total-received').textContent = `${fmtMoney(data.total_received)} đ`;
    document.getElementById('total-refunded').textContent = `${fmtMoney(data.total_refunded)} đ`;
    document.getElementById('total-expense').textContent = `${fmtMoney(data.total_expense)} đ`;
    document.getElementById('net-amount').textContent = `${fmtMoney(data.net_amount)} đ`;
    document.getElementById('period-display').textContent = data.period_label || 'Kỳ dữ liệu hiện tại';
}

function createCashierCell(text, className = '') {
    const cell = document.createElement('td');
    cell.className = className;
    cell.textContent = text ?? '';
    return cell;
}

function createDepositPrintButton(record) {
    if (record.type_raw !== 'deposit' || !record.booking_id) {
        const empty = document.createElement('span');
        empty.className = 'text-muted';
        empty.textContent = '—';
        return empty;
    }
    const label = `In hóa đơn cọc ${record.booking_code || record.booking_id}`;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-icon btn-outline-primary';
    button.setAttribute('aria-label', label);
    button.title = label;
    const icon = document.createElement('i');
    icon.className = 'fas fa-print';
    icon.setAttribute('aria-hidden', 'true');
    button.appendChild(icon);
    button.addEventListener('click', () => openDepositInvoice(record.booking_id));
    return button;
}

function renderCashierTable(records) {
    if (!records.length) {
        renderCashierTableState('empty', 'Chưa có giao dịch', 'Không có khoản thu hoặc hoàn tiền trong kỳ đã chọn.');
        return;
    }
    const tbody = document.getElementById('payment-table-body');
    tbody.replaceChildren();
    const badgeVariants = {info: 'status-badge--info', success: 'status-badge--success', warning: 'status-badge--warning', danger: 'status-badge--danger', secondary: 'status-badge--neutral', primary: 'status-badge--info'};
    records.forEach(record => {
        const row = document.createElement('tr');
        const typeCell = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = `status-badge ${badgeVariants[record.badge_color] || 'status-badge--neutral'}`;
        badge.textContent = record.type_label || 'Khác';
        typeCell.appendChild(badge);
        const noteCell = createCashierCell(record.note || 'Không có ghi chú', 'text-muted');
        const amount = Number(record.amount || 0);
        const amountCell = createCashierCell(`${amount > 0 ? '+' : ''}${fmtMoney(amount)} đ`, `text-end numeric-tabular fw-bold ${amount < 0 ? 'finance-negative' : 'finance-positive'}`);
        const printCell = document.createElement('td');
        printCell.className = 'text-center pe-4';
        printCell.appendChild(createDepositPrintButton(record));
        row.append(
            createCashierCell(record.time || '-', 'ps-4 text-nowrap numeric-tabular'),
            createCashierCell(`#${record.booking_code || '--'}`, 'fw-bold'),
            createCashierCell(record.customer_name || 'Khách'),
            typeCell,
            createCashierCell(record.payment_method_label || '—'),
            createCashierCell(record.collected_by || '—', 'text-muted'),
            noteCell,
            amountCell,
            printCell
        );
        tbody.appendChild(row);
    });
}

function openDepositInvoice(bookingId) {
    if (!bookingId) return;
    window.open(api(`/api/bookings/${bookingId}/deposit-invoice`), '_blank', 'noopener');
}

function printDepositInvoice() {
    clearDepositPrintStatus();
    const bookingId = document.getElementById('deposit-booking-id').value;
    if (!bookingId || Number(bookingId) <= 0) {
        showDepositPrintStatus('Vui lòng nhập Booking ID hợp lệ.');
        return;
    }
    openDepositInvoice(bookingId);
}
