// ==========================================
// static/js/room.js - QUẢN LÝ SƠ ĐỒ PHÒNG
// ==========================================

// Biến toàn cục
let allRooms = [];
let hasLoadedRooms = false;
let currentCheckInRoomNumber = null; // Dùng cho Modal tạo Booking mới
let selectedDepositRatio = null;
let currentBookingQuote = null;

document.addEventListener('DOMContentLoaded', () => {
    loadRoomsData();
    setInterval(loadRoomsData, 30000); // Tự động cập nhật 30s

    document.getElementById('bk-deposit')?.addEventListener('input', () => {
        selectedDepositRatio = null;
        currentBookingQuote = null;
        const hint = document.getElementById('deposit-hint');
        if (hint) hint.textContent = 'Vui lòng bấm nút cọc 50% hoặc 100% để xác nhận lại giá.';
    });
    ['bk-daily-in', 'bk-daily-out', 'bk-hourly-in'].forEach(controlId => {
        document.getElementById(controlId)?.addEventListener('change', resetBookingQuote);
    });
});

// ==========================================
// 1. TẢI DỮ LIỆU TỪ SERVER
// ==========================================
function loadRoomsData() {
    if (!hasLoadedRooms) {
        renderRoomMapState(
            'loading',
            'Đang tải dữ liệu phòng',
            'Vui lòng chờ trong giây lát.'
        );
    }

    fetch(api('/api/rooms') + '?t=' + new Date().getTime())
        .then(res => {
            if (!res.ok) throw new Error(`Server Error: ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            allRooms = Array.isArray(data.rooms) ? data.rooms : [];
            hasLoadedRooms = true;
            updateStats(data.stats);
            renderGrid();
        })
        .catch(err => {
            console.error("Lỗi kết nối:", err);
            renderRoomMapState(
                'error',
                'Không thể tải sơ đồ phòng',
                'Kiểm tra kết nối rồi thử tải lại.',
                true
            );
        });
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

    grid.replaceChildren();

    // Lọc dữ liệu theo dropdown
    const filteredRooms = allRooms.filter(room => {
        if (filter === 'all') return true;
        if (filter === 'occupied') return room.status === 'occupied';
        if (filter === 'available') return room.status === 'available' && room.clean_status === 'cleaned';
        if (filter === 'dirty') return room.clean_status === 'dirty';
        return room.status === filter;
    });

    if (filteredRooms.length === 0) {
        const hasActiveFilter = filter !== 'all';
        renderRoomMapState(
            'empty',
            hasActiveFilter ? 'Không có phòng phù hợp' : 'Chưa có phòng nào',
            hasActiveFilter
                ? 'Thử chọn trạng thái khác hoặc làm mới dữ liệu.'
                : 'Danh sách phòng sẽ xuất hiện tại đây khi có dữ liệu.',
            true
        );
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

function renderRoomMapState(kind, title, description, showRetry = false) {
    const grid = document.getElementById('room-grid');
    if (!grid) return;

    const column = document.createElement('div');
    column.className = 'col-12 room-map-state-column';

    const state = document.createElement('div');
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    state.setAttribute('aria-live', kind === 'error' ? 'assertive' : 'polite');

    const iconWrap = document.createElement('div');
    iconWrap.className = 'data-state__icon';
    const icon = document.createElement('i');
    icon.className = kind === 'loading'
        ? 'fas fa-circle-notch fa-spin'
        : (kind === 'error' ? 'fas fa-cloud-arrow-down' : 'fas fa-bed');
    icon.setAttribute('aria-hidden', 'true');
    iconWrap.appendChild(icon);

    const heading = document.createElement('h2');
    heading.className = 'data-state__title';
    heading.textContent = title;

    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;

    state.append(iconWrap, heading, message);

    if (showRetry) {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions';
        const retryButton = document.createElement('button');
        retryButton.type = 'button';
        retryButton.className = 'btn btn-outline-primary';
        const retryIcon = document.createElement('i');
        retryIcon.className = 'fas fa-rotate-right';
        retryIcon.setAttribute('aria-hidden', 'true');
        const retryLabel = document.createElement('span');
        retryLabel.textContent = 'Làm mới';
        retryButton.append(retryIcon, retryLabel);
        retryButton.addEventListener('click', loadRoomsData);
        actions.appendChild(retryButton);
        state.appendChild(actions);
    }

    column.appendChild(state);
    grid.replaceChildren(column);
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
    const selectedRoom = allRooms.find(
        room => String(room.number) === String(roomNumber)
    );
    const titleEl = document.getElementById('bk-room-number');
    if(titleEl) titleEl.innerText = roomNumber;
    document.getElementById('bk-room-id').value = selectedRoom?.id || '';
    document.getElementById('bk-customer-id').value = '';
    
    if(document.getElementById('bk-phone')) document.getElementById('bk-phone').value = '';
    if(document.getElementById('bk-name')) document.getElementById('bk-name').value = '';
    if(document.getElementById('bk-cccd')) document.getElementById('bk-cccd').value = '';
    if(document.getElementById('bk-address')) document.getElementById('bk-address').value = '';
    if(document.getElementById('bk-note')) document.getElementById('bk-note').value = '';
    setRentalType('daily');
    bootstrap.Tab.getOrCreateInstance(document.getElementById('tab-daily')).show();
    
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
    resetBookingQuote();

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

    if (!phone.trim()) {
        showBookingFormError('Vui lòng nhập số điện thoại khách.', 'bk-phone');
        return;
    }
    if (!name.trim()) {
        showBookingFormError('Vui lòng nhập họ và tên khách.', 'bk-name');
        return;
    }

    let checkIn, checkOut;
    if (type === 'daily') {
        checkIn = document.getElementById('bk-daily-in').value;
        checkOut = document.getElementById('bk-daily-out').value;
    } else {
        checkIn = document.getElementById('bk-hourly-in').value;
        checkOut = document.getElementById('bk-hourly-out').value;
    }

    if (!checkIn) {
        showBookingFormError(
            'Vui lòng chọn thời gian nhận phòng.',
            type === 'daily' ? 'bk-daily-in' : 'bk-hourly-in'
        );
        return;
    }
    if (!checkOut) {
        showBookingFormError(
            'Vui lòng chọn thời gian trả phòng.',
            type === 'daily' ? 'bk-daily-out' : 'bk-hourly-out'
        );
        return;
    }
    if (selectedDepositRatio !== 0.5 && selectedDepositRatio !== 1) {
        showBookingFormError(
            'Bắt buộc chọn cọc 50% hoặc 100% trước khi tạo booking.',
            'bk-deposit'
        );
        return;
    }
    if (!beginBookingSubmission(status)) return;

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
            check_out: checkOut,
            deposit: document.getElementById('bk-deposit').value,
            quote_fingerprint: currentBookingQuote?.fingerprint || null
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            bootstrap.Modal.getInstance(document.getElementById('bookingModal')).hide();
            loadRoomsData();
        } else {
            showBookingFormError(data.msg || 'Không thể tạo đặt phòng.');
        }
    })
    .catch(() => showBookingFormError('Lỗi kết nối máy chủ. Vui lòng thử lại.'))
    .finally(() => endBookingSubmission());
}

// Các hàm hỗ trợ booking
function updateHourlyEnd() {
    const startStr = document.getElementById('bk-hourly-in').value;
    if(!startStr) return;

    const start = new Date(startStr);
    start.setHours(start.getHours() + 2);
    const local = new Date(start.getTime() - start.getTimezoneOffset() * 60000);
    document.getElementById('bk-hourly-out').value = local.toISOString().slice(0, 16);
}

function setRentalType(type) {
    const el = document.getElementById('bk-type');
    if(el) el.value = type;
    resetBookingQuote();
}

function resetBookingQuote() {
    selectedDepositRatio = null;
    currentBookingQuote = null;
    const depositInput = document.getElementById('bk-deposit');
    const hint = document.getElementById('deposit-hint');
    if (depositInput) depositInput.value = 0;
    if (hint) {
        hint.textContent = 'Vui lòng bấm nút cọc 50% hoặc 100% trước khi tạo booking.';
    }
}

async function calculateQuickDeposit(percent = 0.5) {
    const rentalType = document.getElementById('bk-type').value;
    const checkIn = document.getElementById(
        rentalType === 'daily' ? 'bk-daily-in' : 'bk-hourly-in'
    ).value;
    const checkOut = document.getElementById(
        rentalType === 'daily' ? 'bk-daily-out' : 'bk-hourly-out'
    ).value;
    const roomId = document.getElementById('bk-room-id').value;
    const depositInput = document.getElementById('bk-deposit');
    const hint = document.getElementById('deposit-hint');

    if (!roomId || !checkIn || !checkOut) {
        if (hint) hint.textContent = 'Vui lòng chọn đủ phòng và thời gian để tính giá.';
        return;
    }
    if (new Date(checkOut) <= new Date(checkIn)) {
        if (hint) hint.textContent = 'Giờ trả phòng phải sau giờ nhận phòng.';
        return;
    }

    if (hint) hint.textContent = 'Đang tính giá từ hệ thống...';
    try {
        const response = await fetch(api('/api/bookings/calculate-price'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                room_id: roomId,
                check_in: checkIn,
                check_out: checkOut,
                rental_type: rentalType
            })
        });
        const data = await response.json();
        if (!data.success || !data.quote) {
            throw new Error(data.msg || 'Không thể tính giá.');
        }

        currentBookingQuote = data.quote;
        selectedDepositRatio = percent;
        const optionKey = percent === 1 ? 'maximum_100' : 'suggested_50';
        const totalAmount = Number(data.quote.total);
        const depositAmount = Number(
            data.quote.deposit_options?.[optionKey] ?? totalAmount * percent
        );
        depositInput.value = depositAmount;
        if (hint) {
            const percentLabel = percent === 1 ? '100%' : '50%';
            hint.textContent = `Đã chọn cọc ${percentLabel}: ${depositAmount.toLocaleString('vi-VN')} đ (tổng tạm tính ${totalAmount.toLocaleString('vi-VN')} đ).`;
        }
    } catch (error) {
        selectedDepositRatio = null;
        currentBookingQuote = null;
        if (hint) hint.textContent = error.message || 'Không thể kết nối để tính giá.';
    }
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
    card.dataset.state = modifier;
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
    const statusIconWrap = document.createElement('span'); statusIconWrap.className = 'room-card__status-icon';
    const statusIcon = document.createElement('i'); statusIcon.className = `fas ${icon}`; statusIcon.setAttribute('aria-hidden', 'true'); statusIconWrap.appendChild(statusIcon); header.append(left, statusIconWrap);
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
    const badge = document.createElement('span'); badge.className = `status-badge status-badge--${modifier}`; badge.textContent = formatRoomStatus(modifier);
    footer.append(action, badge); card.append(header, body, footer); return card;
}

function formatRoomStatus(status) {
    return ({available: 'Sẵn sàng', booked: 'Chờ nhận', occupied: 'Đang ở', hourly: 'Theo giờ', overdue: 'Quá giờ', dirty: 'Cần dọn', maintenance: 'Bảo trì'})[status] || '—';
}

function formatNoticeTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? (value || '—') : new Intl.DateTimeFormat('vi-VN', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}).format(date);
}
