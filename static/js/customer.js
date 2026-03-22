document.addEventListener('DOMContentLoaded', () => {
    loadCustomers(); // Tải danh sách khi vào trang
});

// 1. TẢI DANH SÁCH (CÓ HỖ TRỢ TÌM KIẾM)
function loadCustomers() {
    const keyword = document.getElementById('search-input').value;
    // Gắn từ khóa vào URL API: /api/customers?q=abc
    const url = keyword ? `/api/customers?q=${encodeURIComponent(keyword)}` : '/api/customers';

    fetch(url)
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('customer-table-body');
            tbody.innerHTML = '';

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Không tìm thấy khách hàng nào</td></tr>';
                return;
            }

            data.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="ps-4 fw-bold text-primary">${c.name}</td>
                    <td><span class="badge bg-light text-dark border">${c.phone}</span></td>
                    <td>${c.cccd || '-'}</td>
                    <td>${c.email || '-'}</td>
                    <td class="text-truncate" style="max-width: 200px;" title="${c.address}">${c.address || '-'}</td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-outline-warning me-1" 
                                onclick="openModal(${c.id}, '${c.name}', '${c.phone}', '${c.cccd}', '${c.email}', '${c.address}')">
                            <i class="fas fa-pen"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteCustomer(${c.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
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

    const url = id ? `/api/customers/${id}` : '/api/customers';
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
        fetch(`/api/customers/${id}`, { method: 'DELETE' })
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