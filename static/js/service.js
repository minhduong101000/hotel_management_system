// =======================================================
// QUẢN LÝ DỊCH VỤ & ORDER (Frontend Logic)
// =======================================================

// --- BIẾN TOÀN CỤC ---
let currentOrderRoom = null; 
let serviceMenu = [];        
let cart = {};               

// 1. HÀM MỞ MODAL ORDER
function openOrderModal(roomNumber) {
    currentOrderRoom = roomNumber;
    cart = {}; // Reset giỏ hàng
    
    // Reset giao diện
    const roomTitle = document.getElementById('modal-room-number');
    if(roomTitle) roomTitle.innerText = roomNumber;
    
    const searchInput = document.getElementById('search-service');
    if(searchInput) searchInput.value = ''; 

    renderCart(); // Render giỏ hàng trống
    loadExistingOrders(roomNumber);
    
    // Mở Modal
    const modalEl = document.getElementById('orderModal');
    if(modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }

    // Gọi API lấy Menu (Cache lại để đỡ gọi nhiều lần)
    if (serviceMenu.length === 0) {
        fetch(api('/api/services'))
            .then(res => res.json())
            .then(data => {
                serviceMenu = data;
                renderServiceList(serviceMenu);
            })
            .catch(err => console.error("Lỗi tải menu: ", err));
    } else {
        renderServiceList(serviceMenu);
    }
}

function loadExistingOrders(roomNumber) {
    const list = document.getElementById('existing-order-list');
    const total = document.getElementById('existing-order-total');
    if (!list || !total) return;

    list.textContent = 'Đang tải món đã gọi...';
    total.textContent = '—';
    fetch(api(`/api/bookings/orders/room/${encodeURIComponent(roomNumber)}`))
        .then(response => response.ok ? response.json() : { items: [], total: 0 })
        .then(data => {
            list.replaceChildren();
            const items = data.items || [];
            if (items.length === 0) {
                list.textContent = 'Chưa có món đã gọi.';
            } else {
                items.forEach(item => {
                    const row = document.createElement('div');
                    row.className = 'existing-order-summary__item';
                    const name = document.createElement('span');
                    name.textContent = item.service_name;
                    const quantity = document.createElement('strong');
                    quantity.textContent = `×${item.quantity}`;
                    row.append(name, quantity);
                    list.appendChild(row);
                });
            }
            total.textContent = `${Number(data.total || 0).toLocaleString('vi-VN')} đ`;
        })
        .catch(() => {
            list.textContent = 'Không tải được món đã gọi.';
            total.textContent = '—';
        });
}

// 2. HÀM RENDER MENU (Có hỗ trợ lọc)
function renderServiceList(data) {
    const list = document.getElementById('service-list');
    if (!list) return;

    list.innerHTML = '';
    
    if(data.length === 0) {
        list.innerHTML = '<div class="text-center p-4 text-muted">Không tìm thấy món nào</div>';
        return;
    }

    data.forEach(item => {
        const priceFormatted = parseInt(item.price).toLocaleString('vi-VN');
        
        // Thêm hiệu ứng hover và nút bấm
        list.innerHTML += `
            <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center p-3" 
                 onclick="addToCart(${item.id})" style="cursor: pointer;">
                <div>
                    <div class="fw-bold text-dark">${item.name}</div>
                    <div class="small text-muted fw-bold">${priceFormatted} đ</div>
                </div>
                <button class="btn btn-sm btn-outline-primary rounded-circle" style="width: 32px; height: 32px;">
                    <i class="fas fa-plus"></i>
                </button>
            </div>
        `;
    });
}

// 3. TÌM KIẾM MÓN (Filter)
function filterService() {
    const input = document.getElementById('search-service');
    if(!input) return;

    const keyword = input.value.toLowerCase();
    const filtered = serviceMenu.filter(s => s.name.toLowerCase().includes(keyword));
    renderServiceList(filtered);
}

// 4. THÊM VÀO GIỎ
function addToCart(id) {
    if (!cart[id]) cart[id] = 0;
    cart[id]++;
    renderCart();
}

// 5. GIẢM SỐ LƯỢNG / XÓA KHỎI GIỎ
function removeFromCart(id) {
    if (cart[id]) {
        cart[id]--;
        if (cart[id] <= 0) delete cart[id];
        renderCart();
    }
}

// 6. RENDER GIỎ HÀNG (CỘT PHẢI)
function renderCart() {
    const cartEl = document.getElementById('selected-items');
    const totalEl = document.getElementById('order-total');
    if (!cartEl || !totalEl) return;

    cartEl.innerHTML = '';
    
    let totalMoney = 0;
    let hasItem = false;

    // Duyệt qua các item trong cart
    for (const [id, qty] of Object.entries(cart)) {
        if (qty > 0) {
            hasItem = true;
            // Tìm thông tin chi tiết món trong menu gốc
            const item = serviceMenu.find(s => s.id == id);
            
            if (item) {
                const sum = item.price * qty;
                totalMoney += sum;
                
                const priceFmt = parseInt(item.price).toLocaleString('vi-VN');
                const sumFmt = sum.toLocaleString('vi-VN');

                cartEl.innerHTML += `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div style="flex: 1;">
                            <div class="fw-bold small">${item.name}</div>
                            <div class="text-muted extra-small">${priceFmt} x ${qty}</div>
                        </div>
                        <div class="d-flex align-items-center">
                            <span class="fw-bold text-primary me-3">${sumFmt}</span>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-secondary" onclick="event.stopPropagation(); removeFromCart(${id})">-</button>
                                <button class="btn btn-outline-secondary" onclick="event.stopPropagation(); addToCart(${id})">+</button>
                            </div>
                        </div>
                    </li>
                `;
            }
        }
    }

    if (!hasItem) {
        cartEl.innerHTML = `
            <div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted opacity-50">
                <i class="fas fa-shopping-basket fa-3x mb-2"></i>
                <span>Chưa chọn món</span>
            </div>`;
    }
    
    totalEl.innerText = totalMoney.toLocaleString('vi-VN');
}

// 7. GỬI ORDER (Thêm dịch vụ mới vào phòng)
function submitOrder() {
    const itemsToSend = [];
    for (const [id, qty] of Object.entries(cart)) {
        if (qty > 0) itemsToSend.push({ id: parseInt(id), qty: qty });
    }

    if (itemsToSend.length === 0) {
        alert("Giỏ hàng đang trống!");
        return;
    }

    // Hiệu ứng disable nút để tránh bấm nhiều lần
    const btn = document.querySelector('#orderModal .btn-success'); // Nút xác nhận
    const originalText = btn ? btn.innerHTML : 'Xác nhận';
    if(btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
    }

    fetch(api('/api/orders/add'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            room_number: currentOrderRoom,
            items: itemsToSend // Cấu trúc khớp với Controller: items = [{id, qty}]
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Ẩn modal sau khi thành công
            const modalEl = document.getElementById('orderModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if(modalInstance) modalInstance.hide();
        } else {
            alert("Lỗi: " + data.msg);
        }
    })
    .catch(err => {
        alert("Lỗi kết nối server: " + err);
    })
    .finally(() => {
        // Reset nút bấm
        if(btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
}

// 8. CẬP NHẬT SỐ LƯỢNG DỊCH VỤ (Dùng trong màn hình Checkout Preview)
// Hàm này được gọi khi người dùng sửa số lượng trực tiếp trên bảng thanh toán và bấm "Lưu"
function saveServiceChanges() {
    const roomNumberEl = document.getElementById('checkout-room-number');
    if (!roomNumberEl) return;
    
    const roomNumber = roomNumberEl.innerText;
    let servicesPayload = [];

    // Duyệt qua các dòng trong bảng dịch vụ (class .service-row cần được set ở HTML)
    document.querySelectorAll('.service-row').forEach(row => {
        // Lấy service_id từ data-attribute
        let id = row.getAttribute('data-id'); 
        // Lấy value từ input
        let qtyInput = row.querySelector('.service-qty-input');
        let qty = qtyInput ? qtyInput.value : 0;

        // Backend yêu cầu key là 'service_id' và 'quantity'
        servicesPayload.push({ 
            service_id: id,   // <--- QUAN TRỌNG: Phải khớp với Controller (item['service_id'])
            quantity: qty 
        });
    });

    // Gọi API cập nhật
    fetch(api('/api/bookings/update_services'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            number: roomNumber,
            services: servicesPayload
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert("Đã cập nhật dịch vụ thành công!");
            
            // Nếu có hàm loadCheckoutPreview (để tính lại tiền), hãy gọi nó
            if (typeof loadCheckoutPreview === 'function') {
                loadCheckoutPreview(roomNumber);
            }
        } else {
            alert("Lỗi cập nhật: " + data.msg);
        }
    })
    .catch(err => {
        console.error(err);
        alert("Lỗi kết nối server khi cập nhật dịch vụ.");
    });
}
