let customerSubmitting = false;

document.addEventListener('DOMContentLoaded', () => {
    loadCustomers(); // Tải danh sách khi vào trang
    document.querySelectorAll('#customerModal input, #customerModal textarea').forEach(control => {
        control.addEventListener('input', clearCustomerFormError);
    });
});

function createCustomerCell(text, className = '') {
    const cell = document.createElement('td');
    if (className) {
        cell.className = className;
    }
    cell.textContent = text || '-';
    return cell;
}

function createCustomerActionButton({ className, iconClass, label, onClick }) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `${className} customer-action-button`;
    button.setAttribute('aria-label', label);
    button.title = label;
    button.addEventListener('click', onClick);

    const icon = document.createElement('i');
    icon.className = iconClass;
    icon.setAttribute('aria-hidden', 'true');
    button.appendChild(icon);

    return button;
}

function renderCustomerTableState(kind, title, description, showRetry = false) {
    const tbody = document.getElementById('customer-table-body');
    if (!tbody) return;

    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = 6;

    const state = document.createElement('div');
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');

    const iconWrap = document.createElement('div');
    iconWrap.className = 'data-state__icon';
    const icon = document.createElement('i');
    icon.className = kind === 'loading'
        ? 'fas fa-circle-notch fa-spin'
        : (kind === 'error' ? 'fas fa-cloud-arrow-down' : 'fas fa-user-group');
    icon.setAttribute('aria-hidden', 'true');
    iconWrap.appendChild(icon);

    const heading = document.createElement('h2');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.append(iconWrap, heading, message);

    if (showRetry) {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-outline-primary';
        retry.addEventListener('click', loadCustomers);
        const retryIcon = document.createElement('i');
        retryIcon.className = 'fas fa-rotate-right';
        retryIcon.setAttribute('aria-hidden', 'true');
        const retryLabel = document.createElement('span');
        retryLabel.textContent = 'Thử lại';
        retry.append(retryIcon, retryLabel);
        actions.appendChild(retry);
        state.appendChild(actions);
    }

    cell.appendChild(state);
    row.appendChild(cell);
    tbody.replaceChildren(row);
}

function createCustomerRow(c) {
    const tr = document.createElement('tr');
    tr.appendChild(createCustomerCell(c.name, 'ps-4 fw-bold text-primary'));

    const phoneCell = document.createElement('td');
    const phoneBadge = document.createElement('span');
    phoneBadge.className = 'badge bg-light text-dark border';
    phoneBadge.textContent = c.phone || '-';
    phoneCell.appendChild(phoneBadge);
    tr.appendChild(phoneCell);

    tr.appendChild(createCustomerCell(c.cccd));
    tr.appendChild(createCustomerCell(c.email));

    const addressCell = createCustomerCell(c.address, 'text-truncate');
    addressCell.style.maxWidth = '200px';
    addressCell.title = c.address || '';
    tr.appendChild(addressCell);

    const actionCell = document.createElement('td');
    actionCell.className = 'text-end pe-4';
    const actionGroup = document.createElement('div');
    actionGroup.className = 'table-row-actions button-group';

    const editButton = createCustomerActionButton({
        className: 'btn btn-icon btn-outline-warning',
        iconClass: 'fas fa-pen',
        label: `Sửa khách hàng ${c.name || ''}`.trim(),
        onClick: () => openModal(c.id, c.name, c.phone, c.cccd, c.email, c.address)
    });

    const deleteButton = createCustomerActionButton({
        className: 'btn btn-icon btn-outline-danger',
        iconClass: 'fas fa-trash',
        label: `Xóa khách hàng ${c.name || ''}`.trim(),
        onClick: () => deleteCustomer(c.id)
    });

    actionGroup.append(editButton, deleteButton);
    actionCell.appendChild(actionGroup);
    tr.appendChild(actionCell);

    return tr;
}

// 1. TẢI DANH SÁCH (CÓ HỖ TRỢ TÌM KIẾM)
function loadCustomers() {
    const keyword = document.getElementById('search-input').value.trim();
    // Gắn từ khóa vào URL API: /api/customers?q=abc
    const url = api(keyword ? `/api/customers?q=${encodeURIComponent(keyword)}` : '/api/customers');
    renderCustomerTableState(
        'loading',
        'Đang tải danh sách khách hàng',
        'Vui lòng chờ trong giây lát.'
    );

    fetch(url)
        .then(res => {
            if (!res.ok) throw new Error(`Không thể tải khách hàng (${res.status})`);
            return res.json();
        })
        .then(data => {
            if (!Array.isArray(data)) throw new Error('Dữ liệu khách hàng không hợp lệ');
            const tbody = document.getElementById('customer-table-body');
            tbody.replaceChildren();

            if (data.length === 0) {
                renderCustomerTableState(
                    'empty',
                    keyword ? 'Không có khách hàng phù hợp' : 'Chưa có khách hàng',
                    keyword
                        ? 'Thử từ khóa khác hoặc kiểm tra lại thông tin tìm kiếm.'
                        : 'Khách hàng mới sẽ xuất hiện tại đây sau khi được thêm.'
                );
                return;
            }

            data.forEach(c => {
                tbody.appendChild(createCustomerRow(c));
            });
        })
        .catch(err => {
            console.error('Lỗi tải khách hàng:', err);
            renderCustomerTableState(
                'error',
                'Không thể tải danh sách khách hàng',
                'Kiểm tra kết nối rồi thử tải lại.',
                true
            );
        });
}

// 2. XỬ LÝ TÌM KIẾM KHI ẤN ENTER
function handleSearch(event) {
    if (event.key === 'Enter') {
        loadCustomers();
    }
}

// 3. MỞ MODAL (Dùng chung cho Thêm và Sửa)
function openModal(id = null, name = '', phone = '', cccd = '', email = '', address = '') {
    clearCustomerFormError();
    document.getElementById('cus-id').value = id || '';
    document.getElementById('cus-name').value = name;
    document.getElementById('cus-phone').value = phone;
    document.getElementById('cus-cccd').value = cccd;
    document.getElementById('cus-email').value = email;
    document.getElementById('cus-address').value = address;

    document.getElementById('modalTitle').innerText = id ? 'Cập nhật Khách Hàng' : 'Thêm Khách Mới';
    
    bootstrap.Modal.getOrCreateInstance(document.getElementById('customerModal')).show();
}

function clearCustomerFormError() {
    const modal = document.getElementById('customerModal');
    const status = document.getElementById('customer-form-status');
    if (!modal || !status) return;
    status.textContent = '';
    status.classList.add('d-none');
    modal.querySelectorAll('[aria-invalid="true"]').forEach(control => {
        control.removeAttribute('aria-invalid');
        if (control.getAttribute('aria-describedby') === status.id) {
            control.removeAttribute('aria-describedby');
        }
    });
}

function showCustomerFormError(message, fieldId = null) {
    const status = document.getElementById('customer-form-status');
    const field = fieldId ? document.getElementById(fieldId) : null;
    if (!status) return;
    clearCustomerFormError();
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

function setCustomerSaveBusy(isBusy) {
    const button = document.getElementById('customer-save-button');
    if (!button) return;
    customerSubmitting = isBusy;
    button.disabled = isBusy;
    button.setAttribute('aria-busy', isBusy ? 'true' : 'false');
    button.innerHTML = isBusy
        ? '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Đang lưu...'
        : '<i class="fas fa-save me-1" aria-hidden="true"></i> Lưu thông tin';
}

// 4. LƯU KHÁCH HÀNG
function saveCustomer() {
    if (customerSubmitting) return;
    const id = document.getElementById('cus-id').value;
    const data = {
        name: document.getElementById('cus-name').value,
        phone: document.getElementById('cus-phone').value,
        cccd: document.getElementById('cus-cccd').value,
        email: document.getElementById('cus-email').value,
        address: document.getElementById('cus-address').value
    };

    if (!data.name.trim()) {
        showCustomerFormError('Vui lòng nhập họ và tên khách hàng.', 'cus-name');
        return;
    }
    if (!data.phone.trim()) {
        showCustomerFormError('Vui lòng nhập số điện thoại khách hàng.', 'cus-phone');
        return;
    }

    const url = api(id ? `/api/customers/${id}` : '/api/customers');
    const method = id ? 'PUT' : 'POST';
    setCustomerSaveBusy(true);
    clearCustomerFormError();

    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(resData => {
        if (resData.success) {
            alert(resData.msg);
            // Ẩn modal
            const modalEl = document.getElementById('customerModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            modal.hide();
            // Load lại bảng
            loadCustomers();
        } else {
            showCustomerFormError(resData.msg || 'Không thể lưu khách hàng.');
        }
    })
    .catch(() => showCustomerFormError('Lỗi kết nối máy chủ. Vui lòng thử lại.'))
    .finally(() => setCustomerSaveBusy(false));
}

// 5. XÓA KHÁCH HÀNG
function deleteCustomer(id) {
    if (confirm('Bạn có chắc chắn muốn xóa khách hàng này?')) {
        fetch(api(`/api/customers/${id}`), { method: 'DELETE' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    loadCustomers();
                } else {
                    alert(data.msg);
                }
            });
    }
}
