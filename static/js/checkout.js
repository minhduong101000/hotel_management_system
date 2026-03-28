// static/js/checkout.js

var currentCheckoutRoom = null; // Lưu số phòng hiện tại
var currentBookingId = null;    // Lưu booking_id quan trọng
var currentBookingRoomId = null; // Lưu booking_room_id cho thao tác checkout
var checkoutIncludeTax = false; // Trạng thái bật/tắt VAT 8%

function bindCheckoutTaxToggle() {
    const taxToggle = document.getElementById('co-tax-toggle');
    if (!taxToggle || taxToggle.dataset.bound === '1') {
        return;
    }

    taxToggle.dataset.bound = '1';
    taxToggle.addEventListener('change', function () {
        checkoutIncludeTax = !!taxToggle.checked;
        if (currentCheckoutRoom) {
            checkOut(currentCheckoutRoom, currentBookingId);
        }
    });
}

/**
 * 1. HÀM GỌI API PREVIEW (Xem trước hóa đơn)
 * Dùng chung cho cả Map và Timeline
 * @param {string} roomNumber - Số phòng (VD: '101')
 * @param {int} bookingId - ID của booking (Optional, ưu tiên nếu có)
 */
function checkOut(roomNumber, bookingId = null) {
    bindCheckoutTaxToggle();
    currentCheckoutRoom = roomNumber;
    // Luôn đồng bộ lại context booking cho lần checkout hiện tại.
    // Tránh giữ booking_id cũ khi mở checkout từ sơ đồ phòng (không truyền bookingId).
    currentBookingId = (bookingId !== null && bookingId !== undefined && bookingId !== '')
        ? bookingId
        : null;
    currentBookingRoomId = null;
    // Chuẩn bị payload gửi lên server
    const payload = {
        number: roomNumber,
        include_tax: checkoutIncludeTax
    };
    if (currentBookingId !== null) {
        payload.booking_id = currentBookingId;
    }

    // Gọi API xem trước hóa đơn
    fetch(api('/api/rooms/preview_checkout'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Cập nhật lại booking_id từ server trả về
            currentBookingId = data.booking_id;
            currentBookingRoomId = data.booking_room_id || null;
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
            checkoutIncludeTax = !!data.include_tax;
            const taxToggle = document.getElementById('co-tax-toggle');
            if (taxToggle) {
                taxToggle.checked = checkoutIncludeTax;
            }

            const taxStatus = document.getElementById('co-tax-status');
            if (taxStatus) {
                taxStatus.innerText = checkoutIncludeTax ? 'Đang bật' : 'Đang tắt';
            }

            const taxSection = document.getElementById('tax-section');
            const taxAmountEl = document.getElementById('co-tax-amount');
            if (checkoutIncludeTax && Number(data.tax_amount || 0) > 0) {
                if (taxSection) taxSection.style.display = 'flex';
                if (taxAmountEl) taxAmountEl.innerText = data.formatted_tax_amount + ' đ';
            } else {
                if (taxSection) taxSection.style.display = 'none';
                if (taxAmountEl) taxAmountEl.innerText = '0 đ';
            }
            
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
            const finalPaymentEl = document.getElementById('co-final-payment');
            finalPaymentEl.innerText = data.formatted_final_amount;
            
            // Nếu khách cọc dư (âm tiền), hiển thị màu đỏ báo hoàn tiền
            if (data.final_amount < 0) {
                finalPaymentEl.classList.remove('text-success');
                finalPaymentEl.classList.add('text-danger');
            } else {
                finalPaymentEl.classList.remove('text-danger');
                finalPaymentEl.classList.add('text-success');
            }

            // 4. Lưu số tiền thực thu vào input ẩn
            const rawInput = document.getElementById('co-amount-raw');
            if(rawInput) rawInput.value = data.final_amount;  

            const taxRawInput = document.getElementById('co-tax-amount-raw');
            if (taxRawInput) taxRawInput.value = Number(data.tax_amount || 0);

            // --- E. HIỆN MODAL ---
            const modalEl = document.getElementById('checkoutModal');
            if (!modalEl.classList.contains('show')) {
                const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
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

    fetch(api('/api/bookings/update_service_quantity'), {
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
 * 4. HÀM XÁC NHẬN THANH TOÁN
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
        amount: amount,
        include_tax: checkoutIncludeTax
    };
    if (currentBookingRoomId) {
        payload.booking_room_id = currentBookingRoomId;
    }
    if (currentBookingId) {
        payload.booking_id = currentBookingId;
    }

    fetch(api('/api/rooms/checkout'), {
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


// =========================================================================
// 5. XỬ LÝ THANH TOÁN ĐOÀN (BỔ SUNG)
// =========================================================================

// Hàm hỗ trợ Format tiền VND (đặt tên riêng để tránh đụng global khác)
const checkoutFormatVND = (num) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(num);
let groupCheckoutIncludeTax = false;

function bindGroupCheckoutTaxToggle() {
    const taxToggle = document.getElementById('gc-tax-toggle');
    if (!taxToggle || taxToggle.dataset.bound === '1') {
        return;
    }

    taxToggle.dataset.bound = '1';
    taxToggle.addEventListener('change', function () {
        groupCheckoutIncludeTax = !!taxToggle.checked;
        if (currentBookingId) {
            openGroupCheckout(currentBookingId);
        }
    });
}

/**
 * Mở Modal hóa đơn đoàn và fetch dữ liệu
 */
function openGroupCheckout(passedBookingId = null) {
    bindGroupCheckoutTaxToggle();
    const editInput = document.getElementById('edit-booking-id');
    const bookingId = passedBookingId || (editInput ? editInput.value : null) || currentBookingId;
    
    if(!bookingId) {
        alert("Không tìm thấy mã Booking tổng của đoàn!");
        return;
    }

    const editModalEl = document.getElementById('editBookingModal');
    if (editModalEl) {
        const editModal = bootstrap.Modal.getInstance(editModalEl);
        if(editModal) editModal.hide();
    }

    const detailModalEl = document.getElementById('bookingDetailModal');
    if (detailModalEl) {
        const detailModal = bootstrap.Modal.getInstance(detailModalEl);
        if (detailModal) detailModal.hide();
    }

    currentBookingId = bookingId;

    const query = groupCheckoutIncludeTax ? '?include_tax=true' : '?include_tax=false';
    fetch(api(`/api/bookings/${bookingId}/group_billing${query}`))
        .then(response => response.json())
        .then(res => {
            if (!res.success) { alert(res.msg); return; }

            const data = res.data;
            document.getElementById('gc-booking-code').textContent = data.booking_code;
            const customerEl = document.getElementById('gc-customer-name');
            if (customerEl) {
                const statusText = data.booking_status || '--';
                const noteText = data.booking_note ? ` | Ghi chú: ${data.booking_note}` : '';
                customerEl.textContent = `${data.customer_name} | SDT: ${data.customer_phone || '--'} | Tạo lúc: ${data.created_at || '--'} | Trạng thái: ${statusText}${noteText}`;
            }
            
            const tbody = document.getElementById('gc-room-list');
            tbody.innerHTML = ''; 

            const statusBadgeClass = (status) => {
                if (status === 'checked_in') return 'bg-warning text-dark';
                if (status === 'booked') return 'bg-primary';
                if (status === 'checked_out') return 'bg-success';
                if (status === 'cancelled') return 'bg-danger';
                return 'bg-secondary';
            };
            
            data.rooms.forEach(room => {
                // Tính phụ thu và lấy chi tiết tóm tắt
                let surchargeTotal = 0;
                let surchargeDetail = "";
                if (room.breakdown) {
                    const surchargeItems = room.breakdown.filter(item => item.label === "Phụ thu phát sinh");
                    surchargeTotal = surchargeItems.reduce((sum, item) => sum + item.amount, 0);
                    // Lấy text mô tả (VD: "Sớm 2.5h, Muộn 1h")
                    surchargeDetail = surchargeItems.map(item => item.detail.replace("Tổng ", "").split(" (")[1]?.replace(")", "") || item.detail).join(", ");
                }

                const serviceLines = (room.service_items || [])
                    .map(s => `${s.name} x${s.quantity}: ${checkoutFormatVND(s.total)}`)
                    .join('<br>');

                const scopeText = room.include_in_settlement ? 'Thanh toán lần này' : 'Đã chốt trước đó';

                tbody.innerHTML += `
                    <tr>
                        <td class="text-start">
                            <div class="fw-bold text-primary">${room.room_name}</div>
                            <small class="badge ${statusBadgeClass(room.status)}" style="font-size: 0.7rem;">${room.status_label || room.status || '--'}</small>
                            <div class="text-muted" style="font-size: 0.72rem;">${scopeText}</div>
                        </td>
                        <td class="text-end">${checkoutFormatVND(room.room_fee - surchargeTotal)}</td>
                        <td class="text-end text-secondary">
                            <div>${checkoutFormatVND(room.service_fee)}</div>
                            <div class="small text-muted" style="font-size: 0.72rem; line-height: 1.25;">${serviceLines || 'Không dùng dịch vụ'}</div>
                        </td>
                        <td class="text-end">
                            <div class="text-danger fw-bold">${checkoutFormatVND(surchargeTotal)}</div>
                            <div class="text-muted small" style="font-size: 0.7rem; line-height: 1;">${surchargeDetail}</div>
                        </td>
                        <td class="text-end fw-bold text-dark">${checkoutFormatVND(room.subtotal)}</td>
                    </tr>
                `;
            });

            document.getElementById('gc-grand-total').textContent = checkoutFormatVND(data.grand_total);
            const taxToggle = document.getElementById('gc-tax-toggle');
            groupCheckoutIncludeTax = !!data.include_tax;
            if (taxToggle) {
                taxToggle.checked = groupCheckoutIncludeTax;
            }

            const taxStatusEl = document.getElementById('gc-tax-status');
            if (taxStatusEl) {
                taxStatusEl.textContent = groupCheckoutIncludeTax ? 'Đang bật' : 'Đang tắt';
            }

            const taxAmountEl = document.getElementById('gc-tax-amount');
            if (taxAmountEl) {
                taxAmountEl.textContent = checkoutFormatVND(data.tax_amount || 0);
            }
            document.getElementById('gc-deposit').textContent = `- ${checkoutFormatVND(data.deposit)}`;
            
            const finalEl = document.getElementById('gc-final-total');
            finalEl.textContent = checkoutFormatVND(data.final_total);
            finalEl.className = data.final_total < 0 
                ? "fw-bold fs-4 text-end text-danger" 
                : "fw-bold fs-4 text-end text-success";

            bootstrap.Modal.getOrCreateInstance(document.getElementById('groupCheckoutModal')).show();
        })
        .catch(err => {
            console.error("Lỗi fetch API billing:", err);
            alert("Có lỗi xảy ra khi lấy dữ liệu hóa đơn đoàn!");
        });
}

/**
 * Submit XÁC NHẬN thanh toán toàn bộ đoàn
 */
function submitGroupCheckout() {
    if(!currentBookingId) {
        alert("Lỗi: Không xác định được ID đoàn để thanh toán.");
        return;
    }

    // Hỏi lại cho chắc chắn
    if(!confirm("Bạn có chắc chắn muốn chốt thanh toán toàn bộ các phòng còn lại của đoàn này?")) {
        return;
    }

    // Disable nút bấm tránh click 2 lần
    const btnConfirm = document.querySelector('#groupCheckoutModal [data-role="group-checkout-confirm"]');
    if(btnConfirm) {
        btnConfirm.disabled = true;
        btnConfirm.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
    }

    // Gọi API Backend để Checkout
    fetch(api(`/api/bookings/${currentBookingId}/group_checkout`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            include_tax: groupCheckoutIncludeTax
        })
    })
    .then(response => response.json())
    .then(res => {
        if(res.success) {
            alert("✅ " + res.msg);
            location.reload(); // Load lại trang để cập nhật giao diện
        } else {
            alert("❌ " + res.msg);
            if(btnConfirm) {
                btnConfirm.disabled = false;
                btnConfirm.innerHTML = '<i class="fas fa-check-circle"></i> XÁC NHẬN THANH TOÁN ĐOÀN';
            }
        }
    })
    .catch(err => {
        console.error("Lỗi submit checkout:", err);
        alert("Có lỗi xảy ra khi thanh toán!");
        if(btnConfirm) {
            btnConfirm.disabled = false;
            btnConfirm.innerHTML = '<i class="fas fa-check-circle"></i> XÁC NHẬN THANH TOÁN ĐOÀN';
        }
    });
}