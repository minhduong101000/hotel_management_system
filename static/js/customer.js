document.addEventListener('DOMContentLoaded', () => {
    loadCustomers(); // Tải danh sách khi vào trang
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
    button.className = className;
    button.setAttribute('aria-label', label);
    button.title = label;
    button.addEventListener('click', onClick);

    const icon = document.createElement('i');
    icon.className = iconClass;
    icon.setAttribute('aria-hidden', 'true');
    button.appendChild(icon);

    return button;
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

    const editButton = createCustomerActionButton({
        className: 'btn btn-sm btn-outline-warning me-1',
        iconClass: 'fas fa-pen',
        label: `Sửa khách hàng ${c.name || ''}`.trim(),
        onClick: () => openModal(c.id, c.name, c.phone, c.cccd, c.email, c.address)
    });

    const deleteButton = createCustomerActionButton({
        className: 'btn btn-sm btn-outline-danger',
        iconClass: 'fas fa-trash',
        label: `Xóa khách hàng ${c.name || ''}`.trim(),
        onClick: () => deleteCustomer(c.id)
    });

    actionCell.append(editButton, deleteButton);
    tr.appendChild(actionCell);

    return tr;
}

// 1. TẢI DANH SÁCH (CÓ HỖ TRỢ TÌM KIẾM)
function loadCustomers() {
    const keyword = document.getElementById('search-input').value;
    // Gắn từ khóa vào URL API: /api/customers?q=abc
    const url = api(keyword ? `/api/customers?q=${encodeURIComponent(keyword)}` : '/api/customers');

    fetch(url)
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('customer-table-body');
            tbody.replaceChildren();

            if (data.length === 0) {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = 6;
                emptyCell.className = 'text-center py-4 text-muted';
                emptyCell.textContent = 'Không tìm thấy khách hàng nào';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
                return;
            }

            data.forEach(c => {
                tbody.appendChild(createCustomerRow(c));
            });
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
    document.getElementById('cus-id').value = id || '';
    document.getElementById('cus-name').value = name;
    document.getElementById('cus-phone').value = phone;
    document.getElementById('cus-cccd').value = cccd;
    document.getElementById('cus-email').value = email;
    document.getElementById('cus-address').value = address;

    document.getElementById('modalTitle').innerText = id ? 'Cập nhật Khách Hàng' : 'Thêm Khách Mới';
    
    bootstrap.Modal.getOrCreateInstance(document.getElementById('customerModal')).show();
}

// 4. LƯU KHÁCH HÀNG
function saveCustomer() {
    const id = document.getElementById('cus-id').value;
    const data = {
        name: document.getElementById('cus-name').value,
        phone: document.getElementById('cus-phone').value,
        cccd: document.getElementById('cus-cccd').value,
        email: document.getElementById('cus-email').value,
        address: document.getElementById('cus-address').value
    };

    if (!data.name || !data.phone) {
        alert("Vui lòng nhập Tên và Số điện thoại!");
        return;
    }

    const url = api(id ? `/api/customers/${id}` : '/api/customers');
    const method = id ? 'PUT' : 'POST';

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
            alert("Lỗi: " + resData.msg);
        }
    })
    .catch(err => alert("Lỗi kết nối server"));
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
