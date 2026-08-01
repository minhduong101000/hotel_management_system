let serviceSubmitting = false;

document.addEventListener('DOMContentLoaded', loadServices);

function createServiceStateIcon(kind) {
    const icons = {
        loading: 'fas fa-circle-notch fa-spin',
        empty: 'fas fa-bell-concierge',
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

function renderServiceTableState(kind, title, description) {
    const tbody = document.getElementById('service-table-body');
    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = 3;
    const state = document.createElement('div');
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');

    const heading = document.createElement('h2');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.append(createServiceStateIcon(kind), heading, message);

    if (kind === 'empty' || kind === 'error') {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        const action = document.createElement('button');
        action.type = 'button';
        action.className = kind === 'empty' ? 'btn btn-primary' : 'btn btn-outline-primary';
        const icon = document.createElement('i');
        icon.className = kind === 'empty' ? 'fas fa-plus' : 'fas fa-rotate-right';
        icon.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        label.textContent = kind === 'empty' ? 'Thêm món mới' : 'Thử tải lại';
        action.append(icon, label);
        if (kind === 'empty') {
            action.addEventListener('click', () => openModal());
        } else {
            action.addEventListener('click', () => loadServices());
        }
        actions.appendChild(action);
        state.appendChild(actions);
    }

    cell.appendChild(state);
    row.appendChild(cell);
    tbody.replaceChildren(row);
}

function loadServices() {
    renderServiceTableState('loading', 'Đang tải danh mục dịch vụ', 'Vui lòng chờ trong giây lát.');
    fetch(api('/api/services'))
        .then(response => {
            if (!response.ok) throw new Error('Không thể tải danh mục dịch vụ.');
            return response.json();
        })
        .then(services => {
            if (!Array.isArray(services)) throw new Error('Dữ liệu dịch vụ không hợp lệ.');
            renderServices(services);
        })
        .catch(error => {
            renderServiceTableState('error', 'Không thể tải danh mục dịch vụ', error.message);
        });
}

function createServiceActionButton(label, iconClass, variant, handler) {
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

function renderServices(services) {
    if (!services.length) {
        renderServiceTableState('empty', 'Chưa có dịch vụ', 'Thêm món đầu tiên để bắt đầu ghi nhận minibar và dịch vụ phòng.');
        return;
    }

    const tbody = document.getElementById('service-table-body');
    tbody.replaceChildren();
    services.forEach(service => {
        const row = document.createElement('tr');

        const nameCell = document.createElement('td');
        nameCell.className = 'ps-4 fw-bold';
        nameCell.textContent = service.name || '-';

        const priceCell = document.createElement('td');
        priceCell.className = 'text-end numeric-tabular fw-semibold';
        priceCell.textContent = `${formatServicePrice(service.price)} đ`;

        const actionCell = document.createElement('td');
        actionCell.className = 'text-end pe-4';
        const actions = document.createElement('div');
        actions.className = 'table-row-actions button-group';
        const serviceName = service.name || 'dịch vụ';
        actions.append(
            createServiceActionButton(`Sửa ${serviceName}`, 'fas fa-pen', 'btn-outline-primary', () => openModal(service.id, service.name, service.price)),
            createServiceActionButton(`Xóa ${serviceName}`, 'fas fa-trash', 'btn-outline-danger', () => deleteService(service.id))
        );
        actionCell.appendChild(actions);
        row.append(nameCell, priceCell, actionCell);
        tbody.appendChild(row);
    });
}

function formatServicePrice(value) {
    const amount = Number(value);
    return Number.isFinite(amount) ? new Intl.NumberFormat('vi-VN').format(amount) : '0';
}

function clearServiceFormStatus() {
    const status = document.getElementById('service-form-status');
    status.textContent = '';
    status.classList.add('d-none');
    document.querySelectorAll('#serviceModal [aria-invalid="true"]').forEach(control => {
        control.removeAttribute('aria-invalid');
        if (control.getAttribute('aria-describedby') === status.id) {
            control.removeAttribute('aria-describedby');
        }
    });
}

function showServiceFormStatus(message, fieldId) {
    clearServiceFormStatus();
    const status = document.getElementById('service-form-status');
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

function showServiceFeedback(message, kind = 'success') {
    const feedback = document.getElementById('service-feedback');
    feedback.className = `alert alert-${kind}`;
    feedback.textContent = message;
}

function openModal(id = null, name = '', price = '') {
    clearServiceFormStatus();
    document.getElementById('service-id').value = id || '';
    document.getElementById('service-name').value = name;
    document.getElementById('service-price').value = price;
    document.getElementById('service-modal-title-text').textContent = id ? 'Cập nhật dịch vụ' : 'Thêm dịch vụ';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('serviceModal')).show();
}

function setServiceSubmitBusy(isBusy) {
    const button = document.getElementById('service-save-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-save';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang lưu' : 'Lưu dịch vụ';
    button.replaceChildren(icon, label);
}

function saveService() {
    if (serviceSubmitting) return;
    const id = document.getElementById('service-id').value;
    const name = document.getElementById('service-name').value.trim();
    const price = document.getElementById('service-price').value;

    if (!name) {
        showServiceFormStatus('Vui lòng nhập tên dịch vụ.', 'service-name');
        return;
    }
    if (Number(price) <= 0) {
        showServiceFormStatus('Đơn giá phải lớn hơn 0.', 'service-price');
        return;
    }

    serviceSubmitting = true;
    setServiceSubmitBusy(true);
    clearServiceFormStatus();
    const url = api(id ? `/api/services/${id}` : '/api/services');
    const method = id ? 'PUT' : 'POST';

    return fetch(url, {
        method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, price}),
    })
        .then(response => {
            if (!response.ok) throw new Error('Không thể lưu dịch vụ.');
            return response.json();
        })
        .then(data => {
            if (!data.success) throw new Error(data.msg || 'Không thể lưu dịch vụ.');
            bootstrap.Modal.getOrCreateInstance(document.getElementById('serviceModal')).hide();
            showServiceFeedback(data.msg || 'Đã lưu dịch vụ.');
            loadServices();
        })
        .catch(error => showServiceFormStatus(error.message))
        .finally(() => {
            serviceSubmitting = false;
            setServiceSubmitBusy(false);
        });
}

function deleteService(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa món này không?')) return;
    fetch(api(`/api/services/${id}`), {method: 'DELETE'})
        .then(response => {
            if (!response.ok) throw new Error('Không thể xóa dịch vụ.');
            return response.json();
        })
        .then(data => {
            showServiceFeedback(data.msg, data.success ? 'success' : 'danger');
            if (data.success) loadServices();
        })
        .catch(error => showServiceFeedback(error.message, 'danger'));
}
