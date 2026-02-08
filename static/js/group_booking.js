/**
 * group_booking.js
 * Xử lý đặt phòng theo đoàn
 * Cập nhật: Fix cứng giờ Check-in (14h) - Check-out (12h) & Sửa lỗi hiển thị UI
 */

// 1. KHI MỞ MODAL: Tự động set ngày mặc định (Hôm nay & Ngày mai)
document.getElementById('groupBookingModal').addEventListener('show.bs.modal', function () {
    // Reset form
    document.getElementById('groupBookingForm').reset();
    document.getElementById('roomSelectionList').innerHTML = '<div class="text-center text-muted mt-5 py-4"><i>Vui lòng chọn ngày và bấm nút "Tìm"</i></div>';
    document.getElementById('availCount').innerText = '0';
    
    // Lấy ngày hiện tại (Local Time) để tránh lệch múi giờ
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


// 2. HÀM TÌM PHÒNG (SEARCH)
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

    // === QUAN TRỌNG: Nối chuỗi giờ cố định (14:00 và 12:00) ===
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


// 3. HÀM HIỂN THỊ DANH SÁCH PHÒNG (RENDER)
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
        // --- FIX LỖI GIAO DIỆN Ở ĐÂY ---
        // Sử dụng col-12 để tiêu đề chiếm hết dòng, mt-3 mb-2 để tạo khoảng cách
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
        
        // Mở container cho các thẻ phòng
        html += `<div class="row g-2 px-2 mb-2">`;

        rooms.forEach(room => {
            totalAvailable++;
            
            // Xử lý hiển thị giá và màu sắc nếu là ngày lễ/cuối tuần
            let priceDisplay = `<div class="small text-muted">${room.price}</div>`;
            let cardClass = "border-secondary";
            let bgClass = "";

            if (room.is_special) {
                priceDisplay = `<div class="small text-danger fw-bold">${room.price} <i class="fas fa-star" style="font-size: 8px;"></i></div>`;
                cardClass = "border-warning"; // Viền vàng cảnh báo giá đặc biệt
                bgClass = "bg-warning bg-opacity-10";
            }

            html += `
                <div class="col-6 col-md-4 col-lg-3">
                    <input type="checkbox" class="btn-check room-checkbox" id="gr_room_${room.id}" value="${room.id}" autocomplete="off">
                    <label class="btn btn-outline-secondary w-100 p-2 d-flex flex-column justify-content-center align-items-center h-100 ${cardClass} ${bgClass}" for="gr_room_${room.id}">
                        <span class="fw-bold fs-5 text-dark">${room.number}</span>
                        ${priceDisplay}
                    </label>
                </div>
            `;
        });

        // Đóng row của nhóm đó
        html += `</div>`;
    }

    container.innerHTML = html;
    document.getElementById('availCount').innerText = totalAvailable;
}


// 4. HÀM GỬI BOOKING (SUBMIT)
function submitGroupBooking() {
    const form = document.getElementById('groupBookingForm');
    
    // Lấy thông tin khách
    const customerName = form.querySelector('input[name="group_name"]').value.trim();
    const customerPhone = form.querySelector('input[name="group_phone"]').value.trim();
    const deposit = form.querySelector('input[name="total_deposit"]').value || 0;
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

    // === QUAN TRỌNG: Lấy ngày và ghép giờ cố định lần nữa ===
    const dateIn = document.getElementById('g_check_in').value;
    const dateOut = document.getElementById('g_check_out').value;
    
    const checkInPayload = dateIn + 'T14:00:00';
    const checkOutPayload = dateOut + 'T12:00:00';

    // Disable nút bấm để tránh double click
    const submitBtn = document.querySelector('#groupBookingModal .modal-footer .btn-success');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';

    // Gửi API
    const payload = {
        customer: {
            name: customerName,
            phone: customerPhone
        },
        room_ids: roomIds,
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
            location.reload(); // Tải lại trang để cập nhật sơ đồ
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

// Helper: Format ngày hiển thị cho đẹp (dd/mm/yyyy)
function formatDateVN(dateStr) {
    if (!dateStr) return '';
    const [yyyy, mm, dd] = dateStr.split('-');
    return `${dd}/${mm}/${yyyy}`;
}