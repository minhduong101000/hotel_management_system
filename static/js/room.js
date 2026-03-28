// ==========================================
// static/js/room.js - QUẢN LÝ SƠ ĐỒ PHÒNG
// ==========================================

// Biến toàn cục
let allRooms = [];
let currentCheckInRoomNumber = null; // Dùng cho Modal tạo Booking mới

document.addEventListener('DOMContentLoaded', () => {
    loadRoomsData();
    setInterval(loadRoomsData, 30000); // Tự động cập nhật 30s
});

// ==========================================
// 1. TẢI DỮ LIỆU TỪ SERVER
// ==========================================
function loadRoomsData() {
    fetch(api('/api/rooms'))
        .then(res => {
            if (!res.ok) throw new Error(`Server Error: ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (data.error) {
                console.error("Lỗi Backend:", data.error);
                return;
            }
            allRooms = data.rooms;
            updateStats(data.stats);
            renderGrid();
        })
        .catch(err => console.error("Lỗi kết nối:", err));
}

function updateStats(stats) {
    if (!stats) return;
    const elAvail = document.getElementById('stat-available');
    const elOcc = document.getElementById('stat-occupied');
    const elDirty = document.getElementById('stat-dirty');
    
    if (elAvail) elAvail.innerText = stats.available;
    if (elOcc) elOcc.innerText = stats.occupied;
    if (elDirty) elDirty.innerText = stats.dirty;
}

// ==========================================
// 2. VẼ LƯỚI PHÒNG (RENDER GRID)
// ==========================================
function renderGrid() {
    const grid = document.getElementById('room-grid');
    const filter = document.getElementById('filter-status').value;
    
    grid.innerHTML = ''; 

    // Lọc dữ liệu theo dropdown
    const filteredRooms = allRooms.filter(room => {
        if (filter === 'all') return true;
        if (filter === 'occupied') return room.status === 'occupied';
        if (filter === 'available') return room.status === 'available' && room.clean_status === 'cleaned';
        if (filter === 'dirty') return room.clean_status === 'dirty';
        return room.status === filter;
    });

    if (filteredRooms.length === 0) {
        grid.innerHTML = '<div class="col-12 text-center text-muted mt-5"><i>Không tìm thấy phòng nào</i></div>';
        return;
    }

    filteredRooms.forEach(room => {
        let cardHtml = '';
        
        // --- TRƯỜNG HỢP 1: PHÒNG CÓ KHÁCH (OCCUPIED) ---
        if (room.status === 'occupied') {
            let statusClass = (room.rental_type === 'hourly') ? 'st-hourly' : 'st-occupied';
            
            // --- [FIX LỖI NULL TẠI ĐÂY] ---
            // Sử dụng ?. để kiểm tra an toàn, nếu customer là null thì lấy chuỗi rỗng
            const safeName = (room.customer_name || '').replace(/'/g, "\\'");
            const safePhone = (room.customer?.phone || '').replace(/'/g, "\\'"); 
            // ------------------------------

            const safeCheckInTime = (room.check_in_time || '');
            const safeCheckOutTime = (room.check_out_expected || '');

            cardHtml = `
                <div class="room-card ${statusClass}" 
                     onclick="openOrderModal('${room.number}')" 
                     style="cursor: pointer; position: relative;">
                     
                    <div class="rc-head d-flex justify-content-between">
                        <div>
                            <div class="rc-num">${room.number}</div>
                            <small>${room.type}</small>
                        </div>
                        
                        <div class="customer-icon-btn" 
                             onclick="event.stopPropagation(); showCustomerInfo('${safeName}', '${safePhone}', '${safeCheckInTime}', '${safeCheckOutTime}')"
                             title="Xem thông tin khách">
                            <i class="fas fa-user-circle fa-2x text-white-50 hover-light"></i>
                        </div>
                    </div>
                    
                    <div class="rc-body">
                        <strong>ĐANG Ở</strong>
                        <div style="font-size: 0.75rem; margin-top: 5px; opacity: 0.8;">
                        </div>
                    </div>
                    
                    <div class="rc-foot mt-2 pt-2 border-top border-white-50 d-flex justify-content-between">
                        <span onclick="event.stopPropagation(); checkOut('${room.number}')" class="btn-action">
                            <i class="fas fa-money-bill"></i> Trả phòng
                        </span>
                        <span class="small opacity-75">...</span>
                    </div>
                </div>`;
        }
        
        // --- TRƯỜNG HỢP 2: PHÒNG BẨN (DIRTY) ---
        else if (room.clean_status === 'dirty') {
            cardHtml = `
                <div class="room-card st-dirty">
                    <div class="rc-head">
                        <div><div class="rc-num">${room.number}</div><small>${room.type}</small></div>
                        <i class="fas fa-broom opacity-50"></i>
                    </div>
                    <div class="rc-body">
                         <button class="btn btn-sm btn-light text-warning fw-bold shadow-sm" onclick="cleanRoom('${room.number}')">
                            <i class="fas fa-check"></i> Dọn xong
                        </button>
                    </div>
                    <div class="rc-foot">
                        <span>Cần dọn</span>
                        <span>Bẩn</span>
                    </div>
                </div>`;
        }
        
        // --- TRƯỜNG HỢP 3: PHÒNG TRỐNG (AVAILABLE) ---
        else if (room.status === 'available') {
            let badgeHtml = '';
            if (room.waiting) {
                badgeHtml = `<div class="position-absolute top-0 end-0 m-1 badge bg-danger text-white shadow-sm" style="z-index: 10;">
                                 <i class="fas fa-exclamation-circle"></i> Chờ: ${room.waiting}
                               </div>`;
            } else if (room.upcoming) {
                badgeHtml = `<div class="position-absolute top-0 end-0 m-1 badge bg-warning text-dark shadow-sm" style="z-index: 10;">
                                 <i class="fas fa-clock"></i> Sắp đến: ${room.upcoming}
                               </div>`;
            }

            cardHtml = `
                <div class="room-card st-free position-relative">
                    ${badgeHtml}
                    <div class="rc-head">
                        <div><div class="rc-num">${room.number}</div><small>${room.type}</small></div>
                        <i class="fas fa-bed opacity-50"></i>
                    </div>
                    <div class="rc-body">
                        <div class="text-center">
                            <h4 class="fw-light mb-0">${room.formatted_price}</h4>
                            <small>VNĐ/đêm</small>
                        </div>
                    </div>
                    <div class="rc-foot">
                        <span onclick="checkIn('${room.number}', ${room.id})" class="btn-action">
                            <i class="fas fa-sign-in-alt"></i> Check-in
                        </span>
                        <span>Sạch</span>
                    </div>
                </div>`;
        }
        // --- TRƯỜNG HỢP 4: BẢO TRÌ ---
        else {
             cardHtml = `
                <div class="room-card bg-secondary text-white">
                    <div class="rc-body text-center pt-4"><h5>BẢO TRÌ</h5></div>
                </div>`;
        }

        const col = document.createElement('div');
        col.className = 'col-xl-2 col-lg-3 col-md-4 col-sm-6'; 
        col.innerHTML = cardHtml;
        grid.appendChild(col);
    });
}

// ==========================================
// 3. LOGIC CHECK-IN
// ==========================================

function checkIn(roomNumber, roomId) {
    console.log(roomNumber, roomId);
    fetch(api(`/api/bookings/upcoming/${roomId}`))
        .then(res => res.json())
        .then(data => {
            if (data.has_booking) {
                const typeText = data.rental_type === 'hourly' ? 'Theo Giờ' : 'Theo Ngày';
                const msg = `⚠️ PHÁT HIỆN ĐẶT PHÒNG TRƯỚC\nPhòng: ${roomNumber}\nKhách hàng: ${data.customer_name}\nBạn có muốn Check-in cho khách này ngay bây giờ?`;

                if (confirm(msg)) {
                    performCheckIn(roomNumber, data.booking_id);
                }
            } else {
                openBookingModal(roomNumber);
            }
        })
        .catch(err => {
            console.error(err);
            openBookingModal(roomNumber);
        });
}

function performCheckIn(roomNumber, bookingId) {
    console.log(roomNumber, bookingId);
    fetch(api('/api/rooms/checkin'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ number: roomNumber, booking_id: bookingId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.msg);
            loadRoomsData();
        } else {
            alert("Lỗi: " + data.msg);
        }
    });
}

// ==========================================
// 4. LOGIC MODAL BOOKING
// ==========================================

function openBookingModal(roomNumber) {
    currentCheckInRoomNumber = roomNumber;
    const titleEl = document.getElementById('bk-room-number');
    if(titleEl) titleEl.innerText = roomNumber;
    
    if(document.getElementById('bk-phone')) document.getElementById('bk-phone').value = '';
    if(document.getElementById('bk-name')) document.getElementById('bk-name').value = '';
    if(document.getElementById('bk-cccd')) document.getElementById('bk-cccd').value = '';
    if(document.getElementById('bk-address')) document.getElementById('bk-address').value = '';
    
    // Set thời gian mặc định
    const now = new Date();
    const nowLocal = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    const inVal = nowLocal.toISOString().slice(0,16);
    
    if(document.getElementById('bk-daily-in')) document.getElementById('bk-daily-in').value = inVal;
    if(document.getElementById('bk-hourly-in')) document.getElementById('bk-hourly-in').value = inVal;
    
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(12, 0, 0, 0);
    const tomLocal = new Date(tomorrow.getTime() - tomorrow.getTimezoneOffset() * 60000);
    if(document.getElementById('bk-daily-out')) document.getElementById('bk-daily-out').value = tomLocal.toISOString().slice(0,16);

    const modalEl = document.getElementById('bookingModal');
    if(modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
    else alert("Hiện chưa booking nào");
}

function submitFullBooking(status) {
    const phone = document.getElementById('bk-phone').value;
    const name = document.getElementById('bk-name').value;
    const cccd = document.getElementById('bk-cccd').value;
    const address = document.getElementById('bk-address').value;
    
    let type = 'daily';
    const activeTab = document.querySelector('#bookingModal .nav-link.active');
    if(activeTab && activeTab.id === 'tab-hourly') type = 'hourly';
    else if(document.getElementById('bk-type')) type = document.getElementById('bk-type').value;

    if(!phone || !name) { alert("Vui lòng nhập tên và SĐT khách!"); return; }

    let checkIn, checkOut;
    if (type === 'daily') {
        checkIn = document.getElementById('bk-daily-in').value;
        checkOut = document.getElementById('bk-daily-out').value;
    } else {
        checkIn = document.getElementById('bk-hourly-in').value;
        checkOut = document.getElementById('bk-hourly-out').value;
    }

    fetch(api('/api/bookings/create'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            room_number: currentCheckInRoomNumber,
            phone: phone, name: name,
            cccd: cccd, address: address,
            rental_type: type,
            status: status,
            check_in: checkIn,
            check_out: checkOut
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            bootstrap.Modal.getInstance(document.getElementById('bookingModal')).hide();
            loadRoomsData();
        } else {
            alert(data.msg);
        }
    });
}

// Các hàm hỗ trợ booking
function updateHourlyEnd() {
    const startStr = document.getElementById('bk-hourly-in').value;
    const duration = parseInt(document.getElementById('bk-duration').value);
    if(!startStr || !duration) return;

    const start = new Date(startStr);
    start.setHours(start.getHours() + duration);
    const local = new Date(start.getTime() - start.getTimezoneOffset() * 60000);
    document.getElementById('bk-hourly-out').value = local.toISOString().slice(0, 16);
}

function setRentalType(type) {
    const el = document.getElementById('bk-type');
    if(el) el.value = type;
}

// ==========================================
// 5. CÁC HÀM TIỆN ÍCH KHÁC
// ==========================================

function cleanRoom(number) {
    if(!confirm("Xác nhận đã dọn xong phòng " + number + "?")) return;
    
    fetch(api('/api/rooms/clean'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ number: number })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) loadRoomsData();
        else alert(data.msg);
    });
}

function showCustomerInfo(name, phone, citime, cotime) {
    document.getElementById('ci-name').innerText = name;
    document.getElementById('ci-phone').innerText = phone;
    document.getElementById('ci-time').innerText = citime;
    document.getElementById('co-time').innerText = cotime;
    
    bootstrap.Modal.getOrCreateInstance(document.getElementById('customerInfoModal')).show();
}