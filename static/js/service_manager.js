document.addEventListener('DOMContentLoaded', loadServices);

// 1. TẢI DANH SÁCH
function loadServices() {
    fetch('/api/services')
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('service-table-body');
            tbody.innerHTML = '';
            
            data.forEach(s => {
                // SỬA ĐOẠN NÀY:
                // 1. parseInt(s.price): Chuyển 15000.00 -> 15000 (số nguyên)
                // 2. .toLocaleString('vi-VN'): Chuyển 15000 -> "15.000"
                const priceFormatted = parseInt(s.price).toLocaleString('vi-VN');

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="ps-4 fw-bold">${s.name}</td>
                    
                    <td>${priceFormatted} đ</td>
                    
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-outline-warning me-2" 
                                onclick="openModal(${s.id}, '${s.name}', ${s.price})"> <i class="fas fa-edit"></i> Sửa
                        </button>
                        <button class="btn btn-sm btn-outline-danger" 
                                onclick="deleteService(${s.id})">
                            <i class="fas fa-trash"></i> Xóa
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        });
}

// 2. MỞ MODAL (Dùng chung cho Thêm và Sửa)
function openModal(id = null, name = '', price = '') {
    // Nếu có ID -> Chế độ Sửa, Không có -> Chế độ Thêm
    document.getElementById('service-id').value = id || ''; 
    document.getElementById('service-name').value = name;
    document.getElementById('service-price').value = price;
    
    document.getElementById('modalTitle').innerText = id ? 'Cập Nhật Dịch Vụ' : 'Thêm Dịch Vụ Mới';
    
    new bootstrap.Modal(document.getElementById('serviceModal')).show();
}

// 3. LƯU (Xử lý thông minh: Nếu có ID là Sửa, không ID là Thêm)
function saveService() {
    const id = document.getElementById('service-id').value;
    const name = document.getElementById('service-name').value;
    const price = document.getElementById('service-price').value;

    if (!name || !price) {
        alert("Vui lòng nhập đủ thông tin!");
        return;
    }

    const url = id ? `/api/services/${id}` : '/api/services';
    const method = id ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, price })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.msg);
            location.reload(); // Tải lại trang để cập nhật bảng
        } else {
            alert("Lỗi: " + data.msg);
        }
    });
}

// 4. XÓA
function deleteService(id) {
    if (confirm('Bạn có chắc chắn muốn xóa món này không?')) {
        fetch(`/api/services/${id}`, { method: 'DELETE' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    loadServices(); // Tải lại bảng mà không cần reload trang
                } else {
                    alert(data.msg);
                }
            });
    }
}