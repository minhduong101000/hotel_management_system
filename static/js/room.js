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
    fetch(api('/api/rooms') + '?t=' + new Date().getTime())
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
        const col = document.createElement('div');
        col.className = 'col-xl-2 col-lg-3 col-md-4 col-sm-6 mb-3';
        col.appendChild(renderRoomCard(room));
        grid.appendChild(col);
    });
    return;
}

function showNoticeConfirm(e, bookingRoomId, guestName, expectedTime, isWaiting, guestPhone = '', deposit = 0) {
    if(e) e.stopPropagation();
    
    // Populate and show the confirmation modal
    document.getElementById('ci-booking-room-id').value = bookingRoomId;
    document.getElementById('ci-guest-name').textContent = guestName;
    document.getElementById('ci-expected-time').textContent = expectedTime || 'Không rõ';
    document.getElementById('ci-guest-phone').textContent = guestPhone || 'Chưa có';
    document.getElementById('ci-deposit').textContent = `${Number(deposit || 0).toLocaleString('vi-VN')} VNĐ`;
    
    const badgeHtml = `<span class="badge bg-${isWaiting ? 'danger' : 'warning text-dark'}"><i class="fas ${isWaiting ? 'fa-exclamation-circle' : 'fa-clock'}"></i> ${isWaiting ? 'Chờ' : 'Sắp đến'}</span>`;
    document.getElementById('ci-type-badge').innerHTML = badgeHtml;
    
    const checkInModal = new bootstrap.Modal(document.getElementById('checkInConfirmModal'));
    checkInModal.show();
}

// ==========================================
// 3. LOGIC CHECK-IN
// ==========================================

function checkIn(roomNumber, roomId) {
    console.log(roomNumber, roomId);
    // Bỏ check API upcoming vì thông tin notices đã được render trực tiếp trên UI
    openBookingModal(roomNumber);
}

function confirmAndCheckIn() {
    const bookingRoomId = Number(document.getElementById('ci-booking-room-id').value);
    if (!Number.isInteger(bookingRoomId) || bookingRoomId <= 0) return;
    const modalEl = document.getElementById('checkInConfirmModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if(modal) modal.hide();

    performCheckIn(bookingRoomId);
}

function performCheckIn(bookingRoomId) {
    console.log(bookingRoomId);
    fetch(api('/api/rooms/checkin'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ booking_room_id: bookingRoomId })
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

function getNearestNotice(notices) {
    if (!Array.isArray(notices) || notices.length === 0) return null;
    return [...notices].sort((left, right) => new Date(left.check_in_expected) - new Date(right.check_in_expected))[0];
}

function showNoticeInfo(notice) {
    showNoticeConfirm(null, notice.booking_room_id, notice.guest_name, notice.check_in_expected, notice.type === 'waiting', notice.guest_phone, notice.deposit);
}

function renderRoomCard(room) {
    let modifier = 'available';
    let icon = 'fa-bed';
    let title = 'TRỐNG';
    if (room.status === 'occupied') { modifier = room.is_overdue ? 'overdue' : (room.rental_type === 'hourly' ? 'hourly' : 'occupied'); icon = room.is_overdue ? 'fa-triangle-exclamation' : 'fa-user'; title = room.is_overdue ? 'QUÁ GIỜ TRẢ' : 'ĐANG Ở'; }
    else if (room.clean_status === 'dirty') { modifier = 'dirty'; icon = 'fa-broom'; title = 'CẦN DỌN'; }
    else if (room.status === 'maintenance') { modifier = 'maintenance'; icon = 'fa-screwdriver-wrench'; title = 'BẢO TRÌ'; }

    const nearestNotice = getNearestNotice(room.notices);
    if (nearestNotice && room.status !== 'occupied') { modifier = 'booked'; icon = 'fa-calendar-check'; title = 'SẮP NHẬN PHÒNG'; }
    const card = document.createElement('article'); card.className = `room-card room-card--${modifier}`;
    if (room.status === 'occupied') {
        card.classList.add('room-card--orderable');
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `Gọi món cho phòng ${room.number}`);
        card.addEventListener('click', () => openOrderModal(room.number));
        card.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openOrderModal(room.number);
            }
        });
    }
    const header = document.createElement('header'); header.className = 'room-card__header';
    const number = document.createElement('strong'); number.className = 'room-card__number'; number.textContent = room.number;
    const type = document.createElement('small'); type.className = 'room-card__type'; type.textContent = room.type;
    const left = document.createElement('div'); left.append(number, type);
    const statusIcon = document.createElement('i'); statusIcon.className = `fas ${icon}`; statusIcon.setAttribute('aria-hidden', 'true'); header.append(left, statusIcon);
    const body = document.createElement('div'); body.className = 'room-card__body';
    const state = document.createElement('strong'); state.className = 'room-card__eyebrow'; state.textContent = title; body.appendChild(state);
    const detail = document.createElement('small'); detail.className = 'room-card__detail';
    detail.textContent = nearestNotice && room.status !== 'occupied' ? formatNoticeTime(nearestNotice.check_in_expected) : (room.status === 'occupied' ? (room.customer_name || 'Khách đang lưu trú') : `${room.formatted_price} VNĐ/đêm`);
    body.appendChild(detail);
    const footer = document.createElement('footer'); footer.className = 'room-card__footer';
    const action = document.createElement('button'); action.type = 'button'; action.className = 'room-card__action'; action.setAttribute('aria-label', `Thao tác cho phòng ${room.number}`);
    if (nearestNotice && room.status !== 'occupied') { action.textContent = 'Xem thông tin'; action.addEventListener('click', () => showNoticeInfo(nearestNotice)); }
    else if (room.status === 'occupied') { action.textContent = 'Trả phòng'; action.addEventListener('click', event => { event.stopPropagation(); checkOut(room.number); }); }
    else if (room.clean_status === 'dirty') { action.textContent = 'Dọn xong'; action.addEventListener('click', () => cleanRoom(room.number)); }
    else if (room.status === 'maintenance') { action.textContent = 'Đang bảo trì'; action.disabled = true; }
    else { action.textContent = 'Đặt / Check-in'; action.addEventListener('click', () => openBookingModal(room.number)); }
    const badge = document.createElement('span'); badge.className = 'status-badge'; badge.textContent = formatRoomStatus(modifier);
    footer.append(action, badge); card.append(header, body, footer); return card;
}

function formatRoomStatus(status) {
    return ({available: 'Sẵn sàng', booked: 'Chờ nhận', occupied: 'Đang ở', hourly: 'Theo giờ', overdue: 'Quá giờ', dirty: 'Cần dọn', maintenance: 'Bảo trì'})[status] || '—';
}

function formatNoticeTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? (value || '—') : new Intl.DateTimeFormat('vi-VN', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}).format(date);
}
