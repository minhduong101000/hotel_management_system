// static/js/checkout.js

var currentCheckoutRoom = null; // Lưu số phòng hiện tại
var currentBookingId = null;    // Lưu booking_id quan trọng

/**
 * 1. HÀM GỌI API PREVIEW (Xem trước hóa đơn)
 * Dùng chung cho cả Map và Timeline
 * @param {string} roomNumber - Số phòng (VD: '101')
 * @param {int} bookingId - ID của booking (Optional, ưu tiên nếu có)
 */
function checkOut(roomNumber, bookingId = null) {
    currentCheckoutRoom = roomNumber;
    // Nếu gọi từ Timeline có ID cụ thể, ta gán luôn vào biến toàn cục
    if (bookingId) {
        currentBookingId = bookingId;
    }
    // Chuẩn bị payload gửi lên server
    const payload = { number: roomNumber };
    if (currentBookingId) {
        payload.booking_id = currentBookingId;
    }

    // Gọi API xem trước hóa đơn
    fetch('/api/rooms/preview_checkout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Cập nhật lại booking_id từ server trả về
            currentBookingId = data.booking_id;
            console.log(data)

            // --- A. ĐIỀN THÔNG TIN CƠ BẢN ---
            document.getElementById('co-room-number').innerText = data.room_number;
            document.getElementById('co-customer').innerText = data.customer_name;
            document.getElementById('co-checkin').innerText = data.check_in;
            document.getElementById('co-checkout').innerText = data.check_out;

            // Loại hình thuê (Ngày/Giờ)
            const typeText = data.rental_type;
            document.getElementById('co-type').innerText = typeText;
            
            // --- B. VẼ BẢNG TIỀN PHÒNG (LOGIC MỚI) ---
            const feeTableBody = document.getElementById('room-fee-table-body');
            feeTableBody.innerHTML = ''; // Xóa dữ liệu cũ
            if (data.bill_details && data.bill_details.length > 0) {
                data.bill_details.forEach(item => {
                    // Tạo dòng tr mới cho bảng
                    const row = `
                        <tr>
                            <td class="fw-bold text-dark">${item.label}</td>
                            <td class="text-muted small">${item.detail}</td>
                            <td class="text-end fw-bold">${parseInt(item.amount).toLocaleString()} đ</td>
                        </tr>
                    `;
                    feeTableBody.insertAdjacentHTML('beforeend', row);
                });
            } else {
                // Fallback nếu không có chi tiết (dùng message tóm tắt cũ)
                feeTableBody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">${data.duration_msg}</td></tr>`;
            }

            // Cập nhật số tổng tiền phòng ở chân bảng (tfoot)
            document.getElementById('co-room-fee-table').innerText = data.formatted_room_fee + ' đ';

            // --- C. RENDER DANH SÁCH DỊCH VỤ ---
            document.getElementById('co-service-fee').innerText = data.formatted_service_fee + ' đ';
            renderServicesInternal(data.services);

            // --- D. XỬ LÝ TỔNG KẾT & CỌC ---
            
            // 1. Tổng hóa đơn (Tiền phòng + Dịch vụ + Phụ thu...)
            document.getElementById('co-total-bill').innerText = data.formatted_total_bill + ' đ'; 

            // 2. Hiển thị dòng Trừ Cọc (nếu có)
            const depositSection = document.getElementById('deposit-section');
            if (data.prepaid_amount && data.prepaid_amount > 0) {
                depositSection.style.display = 'flex';
                document.getElementById('co-deposit').innerText = '- ' + data.formatted_prepaid_amount + ' đ';
            } else {
                depositSection.style.display = 'none';
            }

            // 3. Số tiền Khách Cần Trả (Final Payment = Total - Deposit)
            document.getElementById('co-final-payment').innerText = data.formatted_final_amount;

            // 4. Lưu số tiền thực thu vào input ẩn
            const rawInput = document.getElementById('co-amount-raw');
            if(rawInput) rawInput.value = data.final_amount;  

            // --- E. HIỆN MODAL ---
            const modalEl = document.getElementById('checkoutModal');
            if (!modalEl.classList.contains('show')) {
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            }

        } else {
            alert("Lỗi: " + data.msg);
        }
    })
    .catch(err => {
        console.error(err);
        alert("Lỗi kết nối server!");
    });
}

/**
 * 2. HÀM RENDER DỊCH VỤ (Giữ nguyên)
 */
function renderServicesInternal(services) {
    const serviceSection = document.getElementById('service-section');
    const serviceTbody = document.getElementById('table-services-body');
    serviceTbody.innerHTML = '';

    if (services && services.length > 0) {
        serviceSection.style.display = 'block';
        let htmlRows = '';
        
        services.forEach(item => {
            let price = new Intl.NumberFormat('vi-VN').format(item.price);
            let total = new Intl.NumberFormat('vi-VN').format(item.total);

            htmlRows += `
                <tr class="align-middle">
                    <td>
                        <span class="fw-bold text-dark">${item.name}</span><br>
                        <small class="text-muted">${price} đ</small>
                    </td>
                    
                    <td class="text-end fw-bold">${total} đ</td>

                    <td class="text-center">
                        <div class="input-group input-group-sm justify-content-center">
                            <button class="btn btn-outline-danger" 
                                    type="button"
                                    onclick="changeServiceQty(${item.service_id}, -1, ${item.quantity})">
                                <i class="fas fa-minus"></i>
                            </button>
                            
                            <span class="input-group-text bg-white fw-bold text-primary" style="min-width: 40px; justify-content: center;">
                                ${item.quantity}
                            </span>
                            
                            <button class="btn btn-outline-success" 
                                    type="button"
                                    onclick="changeServiceQty(${item.service_id}, 1, ${item.quantity})">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        });
        serviceTbody.innerHTML = htmlRows;
    } else {
        serviceTbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted fst-italic py-3">Chưa sử dụng dịch vụ</td></tr>';
    }
}

/**
 * 3. HÀM XỬ LÝ CLICK TĂNG/GIẢM DỊCH VỤ (Giữ nguyên)
 */
function changeServiceQty(serviceId, changeValue, currentQty) {
    if (!currentBookingId) {
        alert("Không tìm thấy thông tin Booking!");
        return;
    }

    if (changeValue === -1 && currentQty === 1) {
        const confirmDelete = confirm("Số lượng sẽ về 0. Bạn có chắc muốn XÓA dịch vụ này khỏi hóa đơn không?");
        if (!confirmDelete) return; 
    }
    
    document.body.style.cursor = 'wait';

    fetch('/api/bookings/update_service_quantity', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            booking_id: currentBookingId,
            service_id: serviceId,
            change: changeValue
        })
    })
    .then(res => res.json())
    .then(data => {
        document.body.style.cursor = 'default';
        if (data.success) {
            checkOut(currentCheckoutRoom, currentBookingId);
        } else {
            alert("Lỗi: " + data.msg);
        }
    })
    .catch(err => {
        document.body.style.cursor = 'default';
        console.error(err);
        alert("Lỗi kết nối server");
    });
}

/**
 * 4. HÀM XÁC NHẬN THANH TOÁN (Giữ nguyên)
 */
function confirmCheckout() {
    const amountInput = document.getElementById('co-amount-raw');
    const amount = amountInput ? amountInput.value : 0;
    
    const btnConfirm = document.querySelector('#checkoutModal .btn-success');
    if(btnConfirm) {
        btnConfirm.disabled = true;
        btnConfirm.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
    }

    const payload = { 
        number: currentCheckoutRoom,
        amount: amount 
    };
    if (currentBookingId) {
        payload.booking_id = currentBookingId;
    }

    fetch('/api/rooms/checkout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.msg);
            const modalEl = document.getElementById('checkoutModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if(modal) modal.hide();
            
            location.reload(); 
        } else {
            alert(data.msg);
            if(btnConfirm) {
                btnConfirm.disabled = false;
                btnConfirm.innerHTML = '<i class="fas fa-check-circle me-2"></i> XÁC NHẬN THANH TOÁN';
            }
        }
    })
    .catch(err => {
        alert("Lỗi server: " + err);
        if(btnConfirm) {
            btnConfirm.disabled = false;
            btnConfirm.innerHTML = '<i class="fas fa-check-circle me-2"></i> XÁC NHẬN THANH TOÁN';
        }
    });
}