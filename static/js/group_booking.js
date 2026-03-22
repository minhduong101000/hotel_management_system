/**
 * group_booking.js
 * Xử lý đặt phòng theo đoàn
 * Cập nhật: Tích hợp logic tính tiền cọc nhanh (50%, 100%) nhân chuẩn với số đêm lưu trú
 */

let selectedGroupDepositRatio = null;

// ==========================================
// 1. KHI MỞ MODAL: Tự động set ngày mặc định
// ==========================================
document.getElementById('groupBookingModal').addEventListener('show.bs.modal', function () {
    // Reset form
    document.getElementById('groupBookingForm').reset();
    document.getElementById('roomSelectionList').innerHTML = '<div class="text-center text-muted mt-5 py-4"><i>Vui lòng chọn ngày và bấm nút "Tìm"</i></div>';
    document.getElementById('availCount').innerText = '0';
    
    // Reset dòng text gợi ý cọc
    let hint = document.getElementById('group-deposit-hint');
    if (hint) hint.innerText = '';
    selectedGroupDepositRatio = null;
    
    // Lấy ngày hiện tại (Local Time)
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    
    // Set Check-in = Hôm nay
    document.getElementById('g_check_in').value = `${yyyy}-${mm}-${dd}`;
    
    // Set Check-out = Ngày mai
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const t_yyyy = tomorrow.getFullYear();
    const t_mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
    const t_dd = String(tomorrow.getDate()).padStart(2, '0');
    
    document.getElementById('g_check_out').value = `${t_yyyy}-${t_mm}-${t_dd}`;
});


// ==========================================
// 2. HÀM TÌM PHÒNG (SEARCH)
// ==========================================
function searchRoomsForGroup() {
    const dateIn = document.getElementById('g_check_in').value;
    const dateOut = document.getElementById('g_check_out').value;
    const container = document.getElementById('roomSelectionList');

    // Validate cơ bản
    if (!dateIn || !dateOut) {
        alert("Vui lòng chọn đầy đủ Ngày nhận và Ngày trả!");
        return;
    }

    if (dateIn >= dateOut) {
        alert("Ngày trả phòng phải sau ngày nhận phòng!");
        return;
    }

    // Backend sẽ nhận chuỗi dạng: "2025-01-31T14:00:00"
    const checkInPayload = dateIn + 'T14:00:00';
    const checkOutPayload = dateOut + 'T12:00:00';

    // Hiển thị Loading
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <div class="mt-2 text-muted small">Đang tìm phòng trống từ 14h ${formatDateVN(dateIn)} đến 12h ${formatDateVN(dateOut)}...</div>
        </div>
    `;

    // Gọi API
    fetch('/api/rooms/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            check_in: checkInPayload, 
            check_out: checkOutPayload 
        })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            container.innerHTML = `<div class="alert alert-danger m-3 text-center">${data.msg}</div>`;
            return;
        }

        renderRoomList(data.data);
    })
    .catch(error => {
        console.error('Error:', error);
        container.innerHTML = `<div class="alert alert-danger m-3 text-center">Lỗi kết nối Server!</div>`;
    });
}


// ==========================================
// 3. HÀM HIỂN THỊ DANH SÁCH PHÒNG (RENDER)
// ==========================================
function renderRoomList(groupedData) {
    const container = document.getElementById('roomSelectionList');
    let html = '';
    let totalAvailable = 0;

    // Kiểm tra nếu không có dữ liệu
    if (Object.keys(groupedData).length === 0) {
        container.innerHTML = `<div class="alert alert-warning m-3 text-center">Không tìm thấy phòng trống trong khoảng thời gian này!</div>`;
        document.getElementById('availCount').innerText = '0';
        return;
    }

    // Duyệt qua từng loại phòng
    for (const [type, rooms] of Object.entries(groupedData)) {
        html += `
            <div class="col-12 mt-3 mb-2">
                <div class="d-flex align-items-center border-bottom pb-2">
                    <h6 class="text-primary fw-bold m-0 text-uppercase">
                        <i class="fas fa-layer-group me-2"></i>${type}
                    </h6>
                    <span class="badge bg-light text-secondary ms-2 border">${rooms.length} phòng</span>
                </div>
            </div>
        `;
        
        html += `<div class="row g-2 px-2 mb-2">`;

        rooms.forEach(room => {
            totalAvailable++;
            
            // Xử lý chuỗi giá từ API để lấy ra số nguyên (VD: "500,000" -> 500000)
            let rawPriceNum = 0;
            if (room.price) {
                rawPriceNum = parseInt(room.price.replace(/[,.]/g, ''), 10) || 0;
            }

            // Xử lý hiển thị giá và màu sắc nếu là ngày lễ/cuối tuần
            let priceDisplay = `<div class="small text-muted">${room.price}đ</div>`;
            let cardClass = "border-secondary";
            let bgClass = "";

            if (room.is_special) {
                priceDisplay = `<div class="small text-danger fw-bold">${room.price}đ <i class="fas fa-star" style="font-size: 8px;"></i></div>`;
                cardClass = "border-warning"; 
                bgClass = "bg-warning bg-opacity-10";
            }

            // Thêm data-price="${rawPriceNum}" vào checkbox và onchange event
            html += `
                <div class="col-6 col-md-4 col-lg-3">
                    <input type="checkbox" class="btn-check room-checkbox" id="gr_room_${room.id}" value="${room.id}" data-price="${rawPriceNum}" onchange="handleRoomSelectionChange()" autocomplete="off">
                    <label class="btn btn-outline-secondary w-100 p-2 d-flex flex-column justify-content-center align-items-center h-100 ${cardClass} ${bgClass}" for="gr_room_${room.id}">
                        <span class="fw-bold fs-5 text-dark">${room.number}</span>
                        ${priceDisplay}
                    </label>
                </div>
            `;
        });

        html += `</div>`;
    }

    container.innerHTML = html;
    document.getElementById('availCount').innerText = totalAvailable;
}

// ==========================================
// 4. LOGIC TÍNH TIỀN CỌC THEO ĐOÀN
// ==========================================

// Sự kiện khi Lễ tân tick hoặc bỏ tick 1 phòng
function handleRoomSelectionChange() {
    let selectedCheckboxes = document.querySelectorAll('.room-checkbox:checked');
    let hint = document.getElementById('group-deposit-hint');
    let depositInput = document.getElementById('group_total_deposit'); // ID ô input tiền cọc trong HTML của bạn
    
    if (selectedCheckboxes.length > 0) {
        selectedGroupDepositRatio = null;
        if (depositInput) depositInput.value = 0;
        if (hint) hint.innerHTML = '<span class="text-warning">Vui lòng chọn cọc 50% hoặc 100%.</span>';
    } else {
        // Nếu bỏ tick hết thì reset tiền cọc về 0
        if (depositInput) depositInput.value = 0;
        selectedGroupDepositRatio = null;
        if (hint) hint.innerHTML = '<span class="text-muted">Chưa chọn phòng nào.</span>';
    }
}

// Hàm tính cọc nhanh 50% hoặc 100% (Đã tính kèm Số đêm lưu trú)
function calculateGroupQuickDeposit(ratio) {
    let selectedCheckboxes = document.querySelectorAll('.room-checkbox:checked');
    
    if (selectedCheckboxes.length === 0) {
        alert("Vui lòng tick chọn ít nhất 1 phòng trước khi tính cọc!");
        return;
    }

    // --- BƯỚC 1: TÍNH SỐ ĐÊM LƯU TRÚ ---
    const dateInVal = document.getElementById('g_check_in').value;
    const dateOutVal = document.getElementById('g_check_out').value;
    
    if (!dateInVal || !dateOutVal) return; // Tránh lỗi chưa chọn ngày
    
    const dateIn = new Date(dateInVal);
    const dateOut = new Date(dateOutVal);
    
    // Tính khoảng cách giữa 2 ngày và đổi ra số ngày
    const diffTime = Math.abs(dateOut - dateIn);
    let nights = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    if (nights <= 0) nights = 1; // Đảm bảo tối thiểu 1 đêm

    // --- BƯỚC 2: TÍNH TỔNG TIỀN PHÒNG CỦA 1 ĐÊM ---
    let totalSelectedPricePerNight = 0;
    selectedCheckboxes.forEach(checkbox => {
        let price = parseFloat(checkbox.getAttribute('data-price') || 0);
        totalSelectedPricePerNight += price;
    });

    // --- BƯỚC 3: NHÂN VỚI SỐ ĐÊM ĐỂ RA TỔNG TIỀN & TÍNH CỌC ---
    let totalAmount = totalSelectedPricePerNight * nights;
    let totalDeposit = totalAmount * ratio;
    selectedGroupDepositRatio = ratio;

    // Điền số tiền cọc vào Form
    let depositInput = document.getElementById('group_total_deposit');
    if (depositInput) depositInput.value = totalDeposit;

    // Hiện dòng ghi chú chi tiết cho Lễ tân
    let ratioText = ratio === 1 ? "100%" : "50%";
    let hint = document.getElementById('group-deposit-hint');
    if (hint) {
        hint.innerHTML = `
            <span class="text-success fw-bold">Đã tính cọc (${ratioText}): ${totalDeposit.toLocaleString('vi-VN')} đ</span> <br> 
            <small class="text-muted">(Tổng tiền ${selectedCheckboxes.length} phòng x ${nights} đêm: ${totalAmount.toLocaleString('vi-VN')} đ)</small>
        `;
    }
}


// ==========================================
// 5. HÀM GỬI BOOKING (SUBMIT)
// ==========================================
function submitGroupBooking() {
    const form = document.getElementById('groupBookingForm');
    
    // Lấy thông tin khách
    const customerName = form.querySelector('input[name="group_name"]').value.trim();
    const customerPhone = form.querySelector('input[name="group_phone"]').value.trim();
    
    const cccdEl = form.querySelector('input[name="group_cccd"]');
    const customerCccd = cccdEl ? cccdEl.value.trim() : '';
    
    const addressEl = form.querySelector('input[name="group_address"]');
    const customerAddress = addressEl ? addressEl.value.trim() : '';
    
    // Đọc giá trị cọc từ DOM (nếu dùng ID group_total_deposit)
    const depositInput = document.getElementById('group_total_deposit') || form.querySelector('input[name="total_deposit"]');
    const deposit = depositInput ? parseFloat(depositInput.value) || 0 : 0;
    
    const note = form.querySelector('input[name="note"]').value.trim();

    // Lấy danh sách phòng đã chọn
    const checkboxes = document.querySelectorAll('.room-checkbox:checked');
    const roomIds = Array.from(checkboxes).map(cb => cb.value);

    // Validate
    if (!customerName || !customerPhone) {
        alert("Vui lòng nhập Tên và Số điện thoại trưởng đoàn!");
        return;
    }
    if (roomIds.length === 0) {
        alert("Vui lòng chọn ít nhất 1 phòng!");
        return;
    }

    if (selectedGroupDepositRatio !== 0.5 && selectedGroupDepositRatio !== 1) {
        alert("Bắt buộc chọn cọc 50% hoặc 100% trước khi tạo booking đoàn.");
        return;
    }

    const dateIn = document.getElementById('g_check_in').value;
    const dateOut = document.getElementById('g_check_out').value;
    
    const checkInPayload = dateIn + 'T14:00:00';
    const checkOutPayload = dateOut + 'T12:00:00';

    // Disable nút bấm để tránh double click
    const submitBtn = document.querySelector('#groupBookingModal .modal-footer .btn-success');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';

    // Gửi kèm danh sách giá phòng được chọn để Backend dễ chia tiền cọc
    const selectedRoomData = Array.from(checkboxes).map(cb => {
        return {
            room_id: cb.value,
            price: parseFloat(cb.getAttribute('data-price') || 0)
        }
    });

    const payload = {
        customer: {
            name: customerName,
            phone: customerPhone,
            cccd: customerCccd,
            address: customerAddress
        },
        room_ids: roomIds,
        room_data: selectedRoomData, 
        check_in: checkInPayload,
        check_out: checkOutPayload,
        deposit: deposit,
        note: note
    };

    fetch('/api/bookings/group_create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert("✅ Đặt phòng thành công!\n" + data.msg);
            location.reload(); 
        } else {
            alert("❌ Lỗi: " + data.msg);
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    })
    .catch(err => {
        console.error(err);
        alert("Lỗi hệ thống khi gửi yêu cầu!");
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    });
}

// ==========================================
// HELPER: Format ngày hiển thị
// ==========================================
function formatDateVN(dateStr) {
    if (!dateStr) return '';
    const [yyyy, mm, dd] = dateStr.split('-');
    return `${dd}/${mm}/${yyyy}`;
}

// --- TÍNH NĂNG NHẬN DIỆN KHÁCH CŨ QUA SĐT (BOOKING ĐOÀN) ---
document.addEventListener('DOMContentLoaded', function() {
    const phoneInput = document.getElementById('group_phone');
    const nameInput = document.getElementById('group_name');
    let debounceTimer;

    if (phoneInput && nameInput) {
        phoneInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            const phone = this.value.trim();
            if (phone.length < 4) return;

            debounceTimer = setTimeout(() => {
                fetch(`/api/customers?q=${phone}`)
                    .then(res => res.json())
                    .then(data => {
                        const exactMatch = data.find(c => c.phone === phone);
                        if (exactMatch) {
                            nameInput.value = exactMatch.name;
                            nameInput.style.backgroundColor = '#e8f5e9';
                            setTimeout(() => nameInput.style.backgroundColor = '', 1000);
                        }
                    })
                    .catch(err => console.error("Lỗi tìm khách hàng:", err));
            }, 500);
        });
    }

    const groupDepositInput = document.getElementById('group_total_deposit');
    if (groupDepositInput) {
        groupDepositInput.addEventListener('input', function() {
            selectedGroupDepositRatio = null;
        });
    }
});
