// static/js/timeline_manager.js

var timeline;
var roomMap = {}; // Dùng để map ID phòng -> Số phòng
let timelineData = null;
let timelineViewMode = '3days';
let timelineAnchorDate = new Date();
let selectedDepositRatio = null;
let currentBookingQuote = null;
let bookingDetailServicesCatalog = [];
let bookingDetailServicesLines = [];
let bookingDetailCanEditServices = false;
let bookingDetailRoomLine = { name: '-', price: 0 };
let bookingDetailRoomBreakdown = [];
let bookingDetailRoomFee = 0;
let bookingDetailSidebarTab = 'services';

document.addEventListener('DOMContentLoaded', () => {
    loadTimeline();
});

// ========================================================
// 1. LOAD TIMELINE (VIS.JS)
// ========================================================
function loadTimeline() {
    showTimelineState('loading');
    fetch(api('/api/bookings/timeline'))
        .then(res => {
            if (!res.ok) throw new Error(`Không thể tải Timeline (${res.status})`);
            return res.json();
        })
        .then(data => {
            if (!Array.isArray(data.groups) || !Array.isArray(data.items)) {
                throw new Error('Dữ liệu Timeline không hợp lệ');
            }
            // Lưu map để dùng khi click tạo mới
            roomMap = {};
            data.groups.forEach(g => { roomMap[g.id] = g.room_number || g.content; });
            timelineData = data;
            renderTimeline();
        })
        .catch(err => {
            console.error("Lỗi tải timeline:", err);
            showTimelineState('error', 'Không thể tải Timeline. Vui lòng thử lại.');
        });
}

function startOfDay(value) {
    const date = new Date(value);
    date.setHours(0, 0, 0, 0);
    return date;
}

function getTimelineRange() {
    const start = startOfDay(timelineAnchorDate);
    const end = new Date(start);
    if (timelineViewMode === 'week') {
        const day = (start.getDay() + 6) % 7;
        start.setDate(start.getDate() - day);
        end.setTime(start.getTime());
        end.setDate(end.getDate() + 7);
    } else {
        end.setDate(end.getDate() + (timelineViewMode === 'day' ? 1 : 3));
    }
    return { start, end };
}

function formatTimelineRange(range) {
    const format = { day: '2-digit', month: '2-digit', year: 'numeric' };
    const lastDay = new Date(range.end);
    lastDay.setDate(lastDay.getDate() - 1);
    const startText = range.start.toLocaleDateString('vi-VN', format);
    const endText = lastDay.toLocaleDateString('vi-VN', format);
    return startText === endText ? startText : `${startText} – ${endText}`;
}

function updateTimelineControls() {
    const range = getTimelineRange();
    const label = document.getElementById('timeline-range-label');
    if (label) label.textContent = formatTimelineRange(range);
    ['day', '3days', 'week'].forEach(mode => {
        const control = document.getElementById(`timeline-view-${mode}`);
        if (!control) return;
        const isActive = mode === timelineViewMode;
        control.classList.toggle('active', isActive);
        control.setAttribute('aria-pressed', String(isActive));
    });
}

function setTimelineViewMode(mode) {
    timelineViewMode = mode;
    renderTimeline();
}

function shiftTimeline(direction) {
    const range = getTimelineRange();
    const step = timelineViewMode === 'week' ? 7 : timelineViewMode === 'day' ? 1 : 3;
    timelineAnchorDate = new Date(range.start);
    timelineAnchorDate.setDate(timelineAnchorDate.getDate() + direction * step);
    renderTimeline();
}

function goToToday() {
    timelineAnchorDate = new Date();
    renderTimeline();
}

function applyTimelineStatusFilter() {
    renderTimeline();
}

function getFilteredTimelineItems(items) {
    const filter = document.getElementById('timeline-status-filter')?.value || 'all';
    if (filter === 'all') return items;
    return items.filter(item => {
        if (filter === 'overstay') return item.className?.includes('tl-overstay');
        if (filter === 'booked') return item.status === 'booked';
        return item.status === filter;
    });
}

function showTimelineState(state, message = '') {
    const container = document.getElementById('visualization');
    const stateNode = document.getElementById('timeline-state');
    const emptyNotice = document.getElementById('timeline-empty-notice');
    const statePanels = {
        loading: document.getElementById('timeline-loading-state'),
        empty: document.getElementById('timeline-no-rooms-state'),
        error: document.getElementById('timeline-error-state'),
    };
    if (!container || !stateNode || !emptyNotice || Object.values(statePanels).some(node => !node)) return;

    const isPanelState = state === 'loading' || state === 'error' || state === 'empty';
    const isNoItems = state === 'no-items';
    Object.entries(statePanels).forEach(([panelState, panel]) => {
        panel.classList.toggle('d-none', panelState !== state);
    });
    stateNode.classList.toggle('d-none', !isPanelState);
    emptyNotice.classList.toggle('d-none', !isNoItems);
    container.classList.toggle('d-none', isPanelState);
    stateNode.setAttribute('role', state === 'error' ? 'alert' : 'status');
    stateNode.setAttribute('aria-live', state === 'error' ? 'assertive' : 'polite');

    const errorDescription = document.getElementById('timeline-error-description');
    if (state === 'error' && errorDescription) {
        errorDescription.textContent = message || 'Kiểm tra kết nối rồi thử tải lại.';
    }
}

function renderTimeline() {
    if (!timelineData) return;
    updateTimelineControls();
    if (timelineData.groups.length === 0) {
        if (timeline) timeline.destroy();
        timeline = null;
        showTimelineState('empty');
        return;
    }

    const filteredItems = getFilteredTimelineItems(timelineData.items);
    const container = document.getElementById('visualization');
    const items = new vis.DataSet(filteredItems);
    const groups = new vis.DataSet(timelineData.groups);
    const range = getTimelineRange();
    const options = {
        groupOrder: 'content', orientation: 'top', stack: true, zoomKey: 'ctrlKey', minHeight: '550px',
        start: range.start, end: range.end, locale: 'vi',
        tooltip: { followMouse: true, overflowMethod: 'cap' }
    };

    if (timeline) timeline.destroy();
    timeline = new vis.Timeline(container, items, groups, options);
    showTimelineState(filteredItems.length === 0 ? 'no-items' : 'ready');
    timeline.on('click', function (properties) {
        if (properties.item) {
            const itemData = items.get(properties.item);
            if (itemData) {
                if (itemData.is_finalized || itemData.status === 'checked_out' || itemData.status === 'cancelled') {
                    alert('Booking này đã hoàn tất hoặc đã hủy, không thể mở/sửa trên timeline.');
                    return;
                }
                openEditModal(itemData.id, itemData.booking_id);
            }
        } else if (properties.what === 'background' && properties.group) {
            openCreateModal(properties.group, properties.time);
        }
    });
}

// ========================================================
// 2. MODAL TẠO MỚI (CREATE)
// ========================================================
function openCreateModal(roomId, time) {
    document.getElementById('bk-room-number').innerText = roomMap[roomId] || '...';
    document.getElementById('booking-form').reset();

    // ==========================================
    // THÊM: Lưu roomId vào hidden input để dùng cho tính cọc
    let roomIdInput = document.getElementById('bk-room-id');
    if (roomIdInput) roomIdInput.value = roomId;

    // THÊM: Reset lại text gợi ý tiền cọc mỗi khi mở form mới
    let hintText = document.getElementById('deposit-hint');
    if (hintText) hintText.innerText = '';
    selectedDepositRatio = null;
    // ==========================================

    // Tự động set giờ (+2 tiếng) cho Tab Theo Giờ
    let start = new Date(time);
    let end = new Date(start);
    end.setHours(end.getHours() + 2);

    document.getElementById('bk-hourly-in').value = toLocalISO(start);
    document.getElementById('bk-hourly-out').value = toLocalISO(end);

    // Tự động set ngày (14h hôm nay -> 12h mai) cho Tab Theo Ngày
    let dStart = new Date(start);
    dStart.setHours(14, 0, 0, 0);
    let dEnd = new Date(dStart);
    dEnd.setDate(dEnd.getDate() + 1);
    dEnd.setHours(12, 0, 0, 0);
    
    document.getElementById('bk-daily-in').value = toLocalISO(dStart);
    document.getElementById('bk-daily-out').value = toLocalISO(dEnd);

    setRentalType('daily');
    
    var triggerEl = document.querySelector('#tab-daily');
    if(triggerEl) {
        var tab = new bootstrap.Tab(triggerEl);
        tab.show();
    }
    
    bootstrap.Modal.getOrCreateInstance(document.getElementById('bookingModal')).show();
}

function submitFullBooking(status) {
    const rentalType = document.getElementById('bk-type').value;

    if (selectedDepositRatio !== 0.5 && selectedDepositRatio !== 1) {
        showBookingFormError(
            'Bắt buộc chọn cọc 50% hoặc 100% trước khi tạo booking.',
            'bk-deposit'
        );
        return;
    }
    
    const cccdInput = document.getElementById('bk-cccd');
    const addressInput = document.getElementById('bk-address');
    
    const data = {
        room_number: document.getElementById('bk-room-number').innerText,
        phone: document.getElementById('bk-phone').value,
        customer_id: document.getElementById('bk-customer-id')?.value || null,
        name: document.getElementById('bk-name').value,
        cccd: cccdInput ? cccdInput.value.trim() : '',
        address: addressInput ? addressInput.value.trim() : '',
        rental_type: rentalType,
        status: status, 
        check_in: rentalType === 'daily' ? document.getElementById('bk-daily-in').value : document.getElementById('bk-hourly-in').value,
        check_out: rentalType === 'daily' ? document.getElementById('bk-daily-out').value : document.getElementById('bk-hourly-out').value,
        deposit: document.getElementById('bk-deposit').value,
        quote_fingerprint: currentBookingQuote?.fingerprint || null,
        note: document.getElementById('bk-note').value
    };

    if (!data.phone.trim()) {
        showBookingFormError('Vui lòng nhập số điện thoại khách.', 'bk-phone');
        return;
    }
    if (!data.check_in) {
        showBookingFormError(
            'Vui lòng chọn thời gian nhận phòng.',
            rentalType === 'daily' ? 'bk-daily-in' : 'bk-hourly-in'
        );
        return;
    }
    if (!data.check_out) {
        showBookingFormError(
            'Vui lòng chọn thời gian trả phòng.',
            rentalType === 'daily' ? 'bk-daily-out' : 'bk-hourly-out'
        );
        return;
    }
    if (!beginBookingSubmission(status)) return;

    fetch(api('/api/bookings/create'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(d => {
        if(d.success) {
            alert(d.msg);
            bootstrap.Modal.getInstance(document.getElementById('bookingModal')).hide();
            loadTimeline(); 
        } else {
            if (d.code === 'customer_phone_ambiguous') {
                renderCustomerCandidates(d.candidates || []);
                showBookingFormError(
                    'Có nhiều khách dùng số điện thoại này. Vui lòng chọn đúng khách.',
                    'bk-phone'
                );
                return;
            }
            showBookingFormError(d.msg || 'Không thể tạo đặt phòng.');
        }
    })
    .catch(() => showBookingFormError('Lỗi kết nối máy chủ. Vui lòng thử lại.'))
    .finally(() => endBookingSubmission());
}

function renderCustomerCandidates(candidates) {
    const container = document.getElementById('bk-customer-candidates');
    const nameInput = document.getElementById('bk-name');
    const customerIdInput = document.getElementById('bk-customer-id');
    if (!container || !nameInput || !customerIdInput) return;

    container.classList.remove('d-none');
    container.innerHTML = '<div class="small fw-semibold text-secondary mb-1">Chọn khách dùng chung SĐT</div>';
    candidates.forEach(customer => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-sm btn-outline-primary me-1 mb-1';
        button.textContent = `${customer.name || 'Khách chưa tên'}${customer.cccd ? ` · ${customer.cccd}` : ''}`;
        button.setAttribute('aria-label', `Chọn khách ${customer.name || ''}`);
        button.addEventListener('click', () => {
            customerIdInput.value = customer.id;
            nameInput.value = customer.name || '';
            container.classList.add('d-none');
            container.replaceChildren();
        });
        container.appendChild(button);
    });
}

// ========================================================
// 3. MODAL CHỈNH SỬA (EDIT) & LƯU THAY ĐỔI
// ========================================================

// SỬA: Nhận cả bookingRoomId (để sửa dòng này) và bookingId (để quản lý đoàn)
function openEditModal(bookingRoomId, bookingId) {
    // Lưu ID vào hidden input để dùng lúc Save
    document.getElementById('edit-booking-room-id').value = bookingRoomId; 
    document.getElementById('edit-booking-id').value = bookingId || ''; 

    // Bước 1: Load danh sách phòng
    fetch(api('/api/rooms')).then(r => r.json()).then(rData => {
        const sel = document.getElementById('edit-room-select');
        sel.innerHTML = '';
        let rooms = rData.rooms || rData; 
        rooms.forEach(r => {
            sel.innerHTML += `<option value="${r.id}">${r.number || r.room_number}</option>`;
        });

        // Bước 2: Lấy chi tiết BookingRoom (để điền giờ cụ thể của phòng này)
        return fetch(api('/api/bookings/' + bookingRoomId)); 
    }).then(r => r.json()).then(data => {
        if (data.success === false) {
            alert(data.msg || 'Không thể mở booking này.');
            return;
        }
        
        // Điền dữ liệu vào form
        document.getElementById('edit-id').innerText = data.booking_id; // Hiển thị mã đoàn
        document.getElementById('edit-customer').value = data.customer_name;
        document.getElementById('edit-room-select').value = data.room_id;
        document.getElementById('edit-status').value = data.status;

        // Giờ check-in/out của RIÊNG phòng này
        document.getElementById('edit-checkin').value = data.check_in;
        document.getElementById('edit-checkout').value = data.check_out;
        
        // Tiền cọc
        document.getElementById('edit-deposit').value = data.deposit;
        
        // CCCD & Địa chỉ
        const cccdEl = document.getElementById('edit-cccd');
        const addrEl = document.getElementById('edit-address');
        if(cccdEl) cccdEl.value = data.customer_cccd || '';
        if(addrEl) addrEl.value = data.customer_address || '';
        
        toggleRefundSection();

        const btnCheckIn = document.getElementById('btn-checkin-timeline');
        const btnCheckout = document.getElementById('btn-checkout-timeline');
        const btnGroupCheckout = document.getElementById('btn-group-checkout');
        const btnReschedule = document.getElementById('btn-reschedule-booking');
        
        const isCheckedIn = (data.status === 'checked_in');

        if (btnCheckIn) {
            // Chỉ hiện nút Check-in nếu trạng thái là 'pending' hoặc 'booked'
            btnCheckIn.style.display = (data.status === 'pending' || data.status === 'booked') ? 'inline-block' : 'none';
        }

        if (btnCheckout) {
            // Chỉ hiện nút Thanh toán lẻ nếu đã Check-in
            btnCheckout.style.display = isCheckedIn ? 'inline-block' : 'none';
        }

        if (btnGroupCheckout) {
            // Chỉ hiện nút Thanh toán đoàn nếu đã Check-in VÀ là đoàn
            if (isCheckedIn && (data.is_group || data.room_count > 1)) { 
                btnGroupCheckout.style.display = 'inline-block';
            } else {
                btnGroupCheckout.style.display = 'none';
            }
        }
        if (btnReschedule) {
            btnReschedule.style.display = data.status === 'booked' ? 'inline-block' : 'none';
        }
        // ---------------------------------------------------------

        bootstrap.Modal.getOrCreateInstance(document.getElementById('editBookingModal')).show();
    })
    .catch(err => console.error(err));
}

function saveBookingChanges() {
    // Lấy ID chính xác của dòng cần sửa (BookingRoom)
    const bookingRoomId = document.getElementById('edit-booking-room-id').value;
    const bookingId = document.getElementById('edit-booking-id').value; // Dùng nếu hủy cả đơn
    const status = document.getElementById('edit-status').value;

    if (!bookingRoomId) return;

    // --- TRƯỜNG HỢP 1: HỦY PHÒNG ---
    if (status === 'cancelled') {
        if (!confirm("Bạn có chắc chắn muốn HỦY đơn đặt phòng này không?")) return;

        const refundReason = document.getElementById('refund-reason')?.value.trim() || '';
        if (!refundReason) {
            alert('Vui lòng nhập lý do hủy.');
            document.getElementById('refund-reason')?.focus();
            return;
        }

        fetch(api('/api/bookings/cancel'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                booking_room_id: parseInt(bookingRoomId),
                booking_id: parseInt(bookingId),
                reason: refundReason
            })
        })
        .then(r => r.json())
        .then(d => {
            if(d.success) {
                alert(d.msg);
                bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();
                loadTimeline();
            } else {
                alert(d.msg);
            }
        });
    } 
    // --- TRƯỜNG HỢP 2: CẬP NHẬT THÔNG TIN (ĐỔI PHÒNG, ĐỔI GIỜ) ---
    else {
        const data = {
            booking_id: bookingId,
            booking_room_id: bookingRoomId, // QUAN TRỌNG: Gửi ID này để biết sửa thanh nào trên timeline
            room_id: document.getElementById('edit-room-select').value,
            status: status,
            check_in: document.getElementById('edit-checkin').value,
            check_out: document.getElementById('edit-checkout').value,
            deposit: document.getElementById('edit-deposit').value,
            customer_name: document.getElementById('edit-customer').value,
            customer_cccd: document.getElementById('edit-cccd').value,
            customer_address: document.getElementById('edit-address').value
        };

        fetch(api('/api/bookings/update'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        })
        .then(r => r.json())
        .then(d => {
            if(d.success) {
                alert("Cập nhật thành công!");
                bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();
                loadTimeline();
            } else {
                alert(d.msg);
            }
        });
    }
}

let rescheduleSubmitting = false;

function showRescheduleStatus(message, level = 'danger', fieldId = null) {
    const status = document.getElementById('reschedule-status');
    const field = fieldId ? document.getElementById(fieldId) : null;
    if (!status) return;
    status.textContent = message || '';
    status.className = `alert alert-${level}`;
    status.classList.toggle('d-none', !message);
    document.querySelectorAll('#rescheduleModal [aria-invalid="true"]').forEach(control => {
        control.removeAttribute('aria-invalid');
        if (control.getAttribute('aria-describedby') === status.id) {
            control.removeAttribute('aria-describedby');
        }
    });
    if (!message) return;
    if (field) {
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', status.id);
        field.focus();
    } else if (level === 'danger' || level === 'warning') {
        status.focus();
    }
}

function setRescheduleButtonBusy(button, busy, busyText, idleHtml) {
    if (!button) return;
    button.disabled = busy;
    button.setAttribute('aria-busy', busy ? 'true' : 'false');
    button.innerHTML = busy
        ? `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>${busyText}`
        : idleHtml;
}

function rescheduleInvalidField(data, requireReason = false) {
    if (!data.room_id) return 'reschedule-room-select';
    if (!data.check_in) return 'reschedule-checkin';
    if (!data.check_out) return 'reschedule-checkout';
    if (requireReason && !data.reason) return 'reschedule-reason';
    if (new Date(data.check_out) <= new Date(data.check_in)) {
        return 'reschedule-checkout';
    }
    return null;
}

function resetRescheduleAvailability() {
    document.getElementById('reschedule-price-summary').classList.add('d-none');
    document.getElementById('reschedule-submit').disabled = true;
    showRescheduleStatus('');
}

function openRescheduleModal() {
    const bookingRoomId = document.getElementById('edit-booking-room-id').value;
    if (!bookingRoomId) return;

    const roomSelect = document.getElementById('reschedule-room-select');
    const currentRoomId = document.getElementById('edit-room-select').value;
    roomSelect.replaceChildren();

    fetch(api('/api/rooms'))
        .then(response => response.json())
        .then(data => {
            const rooms = data.rooms || data;
            rooms.forEach(room => {
                const option = document.createElement('option');
                option.value = room.id;
                option.textContent = `${room.number || room.room_number} — ${room.type || room.room_type || 'Phòng'}`;
                roomSelect.appendChild(option);
            });
            roomSelect.value = currentRoomId;
            document.getElementById('reschedule-booking-room-id').value = bookingRoomId;
            document.getElementById('reschedule-checkin').value = document.getElementById('edit-checkin').value;
            document.getElementById('reschedule-checkout').value = document.getElementById('edit-checkout').value;
            document.getElementById('reschedule-reason').value = '';
            document.getElementById('reschedule-price-keep').checked = true;
            resetRescheduleAvailability();
            roomSelect.onchange = resetRescheduleAvailability;
            document.getElementById('reschedule-checkin').onchange = resetRescheduleAvailability;
            document.getElementById('reschedule-checkout').onchange = resetRescheduleAvailability;
            bootstrap.Modal.getOrCreateInstance(document.getElementById('rescheduleModal')).show();
        })
        .catch(() => alert('Không thể tải danh sách phòng. Vui lòng thử lại.'));
}

function renderReschedulePriceSummary(data) {
    const summary = document.getElementById('reschedule-price-summary');
    const status = document.getElementById('reschedule-availability-status');
    const difference = Number(data.difference || 0);
    summary.classList.remove('d-none');
    status.textContent = 'Phòng trống';
    status.className = 'badge text-bg-success';
    document.getElementById('reschedule-locked-amount').textContent = formatVND(data.locked_amount);
    document.getElementById('reschedule-current-amount').textContent = formatVND(data.current_amount);
    const differenceEl = document.getElementById('reschedule-difference');
    differenceEl.textContent = `${difference > 0 ? '+' : ''}${formatVND(difference)}`;
    differenceEl.className = difference > 0 ? 'text-danger' : (difference < 0 ? 'text-success' : 'text-dark');
}

function getReschedulePayload() {
    return {
        booking_room_id: Number(document.getElementById('reschedule-booking-room-id').value),
        room_id: Number(document.getElementById('reschedule-room-select').value),
        check_in: document.getElementById('reschedule-checkin').value,
        check_out: document.getElementById('reschedule-checkout').value,
        reason: document.getElementById('reschedule-reason').value.trim(),
        price_mode: document.querySelector('input[name="reschedule-price-mode"]:checked').value,
    };
}

function validateReschedulePayload(data, requireReason = false) {
    if (!data.room_id || !data.check_in || !data.check_out || (requireReason && !data.reason)) {
        return 'Vui lòng điền đủ phòng, thời gian và lý do dời lịch.';
    }
    if (new Date(data.check_out) <= new Date(data.check_in)) {
        return 'Thời gian trả phòng phải sau thời gian nhận phòng.';
    }
    return '';
}

function checkRescheduleAvailability() {
    const data = getReschedulePayload();
    const error = validateReschedulePayload(data);
    if (error) {
        showRescheduleStatus(error, 'danger', rescheduleInvalidField(data));
        return;
    }

    const button = document.getElementById('reschedule-check-availability');
    setRescheduleButtonBusy(
        button,
        true,
        'Đang kiểm tra...',
        '<i class="fas fa-search me-1" aria-hidden="true"></i>Kiểm tra phòng trống'
    );
    showRescheduleStatus('Đang kiểm tra phòng trống...', 'info');
    fetch(api('/api/bookings/reschedule/availability'), {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
    })
        .then(response => response.json())
        .then(result => {
            if (!result.available) {
                resetRescheduleAvailability();
                showRescheduleStatus(
                    result.msg || 'Phòng không phù hợp trong khoảng thời gian đã chọn.',
                    'danger'
                );
                return;
            }
            renderReschedulePriceSummary(result);
            document.getElementById('reschedule-submit').disabled = false;
            showRescheduleStatus('Phòng còn trống. Vui lòng kiểm tra giá trước khi xác nhận.', 'success');
        })
        .catch(() => showRescheduleStatus(
            'Không thể kiểm tra phòng trống. Vui lòng thử lại.',
            'danger'
        ))
        .finally(() => {
            setRescheduleButtonBusy(
                button,
                false,
                '',
                '<i class="fas fa-search me-1" aria-hidden="true"></i>Kiểm tra phòng trống'
            );
        });
}

function submitRescheduleBooking() {
    if (rescheduleSubmitting) return;
    const data = getReschedulePayload();
    const error = validateReschedulePayload(data, true);
    if (error) {
        showRescheduleStatus(
            error,
            'danger',
            rescheduleInvalidField(data, true)
        );
        return;
    }
    if (document.getElementById('reschedule-submit').disabled) {
        showRescheduleStatus(
            'Vui lòng kiểm tra phòng trống trước khi xác nhận.',
            'warning'
        );
        return;
    }

    const submitButton = document.getElementById('reschedule-submit');
    rescheduleSubmitting = true;
    setRescheduleButtonBusy(
        submitButton,
        true,
        'Đang dời lịch...',
        '<i class="fas fa-check me-1" aria-hidden="true"></i>Xác nhận dời lịch'
    );
    showRescheduleStatus('Đang lưu thay đổi lịch đặt phòng...', 'info');
    fetch(api('/api/bookings/reschedule'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                showRescheduleStatus(
                    data.msg || 'Không thể dời lịch đặt phòng.',
                    'danger'
                );
                return;
            }
            bootstrap.Modal.getInstance(document.getElementById('rescheduleModal')).hide();
            bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();
            alert(data.msg || 'Đã dời lịch đặt phòng.');
            loadTimeline();
        })
        .catch(() => showRescheduleStatus(
            'Không thể kết nối để dời lịch. Vui lòng thử lại.',
            'danger'
        ))
        .finally(() => {
            rescheduleSubmitting = false;
            setRescheduleButtonBusy(
                submitButton,
                false,
                '',
                '<i class="fas fa-check me-1" aria-hidden="true"></i>Xác nhận dời lịch'
            );
        });
}

function formatVND(amount) {
    const num = Number(amount || 0);
    return num.toLocaleString('vi-VN') + ' đ';
}

function parseDateInput(value) {
    if (!value) return null;
    const dt = new Date(value);
    return Number.isNaN(dt.getTime()) ? null : dt;
}

function bdUpdateStayDuration() {
    const checkInEl = document.getElementById('bd-checkin');
    const checkOutEl = document.getElementById('bd-checkout');
    const rentalTypeEl = document.getElementById('bd-rental-type');
    const stayEl = document.getElementById('bd-stay-duration');
    const badgeEl = document.getElementById('bd-duration-badge');
    if (!checkInEl || !checkOutEl || !rentalTypeEl || !stayEl || !badgeEl) return;

    const inDt = parseDateInput(checkInEl.value);
    const outDt = parseDateInput(checkOutEl.value);
    if (!inDt || !outDt || outDt <= inDt) {
        stayEl.textContent = '0 ngày';
        badgeEl.textContent = 'Đang sử dụng: 0 ngày';
        return;
    }

    const diffHours = (outDt - inDt) / (1000 * 60 * 60);
    const rentalType = rentalTypeEl.value || 'daily';
    const stayText = rentalType === 'hourly'
        ? `${Math.max(1, Math.ceil(diffHours))} giờ`
        : `${Math.max(1, Math.ceil(diffHours / 24))} ngày`;

    stayEl.textContent = stayText;
    badgeEl.textContent = `Đang sử dụng: ${stayText}`;
}

function bdFilterServiceCatalog() {
    renderBookingDetailServiceCatalog();
}

function renderBookingDetailServiceCatalog() {
    const grid = document.getElementById('bd-service-catalog-grid');
    const countEl = document.getElementById('bd-service-count');
    const searchEl = document.getElementById('bd-service-search');
    if (!grid || !countEl || !searchEl) return;

    const keyword = (searchEl.value || '').trim().toLowerCase();
    const filtered = bookingDetailServicesCatalog.filter(s =>
        !keyword || String(s.name || '').toLowerCase().includes(keyword)
    );

    countEl.textContent = filtered.length;

    if (!filtered.length) {
        grid.innerHTML = '<div class="col-12 text-center text-muted small py-4">Không có dịch vụ phù hợp</div>';
        return;
    }

    const disabledAttr = bookingDetailCanEditServices ? '' : 'disabled';
    grid.innerHTML = filtered.map(s => `
        <div class="col-12">
            <div class="bd-service-item">
                <div>
                    <div class="fw-bold">${s.name || 'Dich vu'}</div>
                    <div class="small text-muted">${formatVND(s.price || 0)}</div>
                </div>
                <button type="button" class="btn btn-sm btn-outline-success" onclick="bdAddServiceById(${Number(s.id)})" ${disabledAttr}>
                    <i class="fas fa-plus"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function renderBookingDetailServices() {
    const body = document.getElementById('bd-invoice-table-body');
    const totalEl = document.getElementById('bd-invoice-total');
    if (!body || !totalEl) return;

    let rows = '';
    let stt = 1;
    let total = 0;

    if (bookingDetailRoomBreakdown.length) {
        rows += bookingDetailRoomBreakdown.map((item) => {
            const amount = Number(item.amount || 0);
            total += amount;
            const detailText = item.detail ? `<div class="small text-muted">${item.detail}</div>` : '';
            return `
                <tr>
                    <td class="text-center">${stt++}</td>
                    <td><strong>${item.label || 'Tiền phòng'}</strong>${detailText}</td>
                    <td class="text-center">1</td>
                    <td class="text-end">${formatVND(amount)}</td>
                    <td class="text-end fw-bold">${formatVND(amount)}</td>
                </tr>
            `;
        }).join('');
    } else {
        const roomAmount = Number(bookingDetailRoomLine.price || 0);
        total += roomAmount;
        rows += `
            <tr>
                <td class="text-center">${stt++}</td>
                <td><strong>${bookingDetailRoomLine.name || 'Tiền phòng'}</strong></td>
                <td class="text-center">1</td>
                <td class="text-end">${formatVND(roomAmount)}</td>
                <td class="text-end fw-bold">${formatVND(roomAmount)}</td>
            </tr>
        `;
    }

    if (bookingDetailServicesLines.length) {
        rows += bookingDetailServicesLines.map((line, idx) => {
            const qty = Number(line.quantity || 0);
            const lineTotal = qty * Number(line.price || 0);
            total += lineTotal;
            const qtyCell = bookingDetailCanEditServices
                ? `<div class="d-flex justify-content-center align-items-center gap-1"><button type="button" class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="bdChangeServiceQty(${idx}, -1)">-</button><span class="fw-bold px-1">${qty}</span><button type="button" class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="bdChangeServiceQty(${idx}, 1)">+</button><button type="button" class="btn btn-sm btn-outline-danger py-0 px-2" onclick="bdRemoveServiceLine(${idx})">x</button></div>`
                : `<span class="fw-bold">${qty}</span>`;
            return `
                <tr>
                    <td class="text-center">${stt++}</td>
                    <td>${line.name || 'Dich vu'}</td>
                    <td class="text-center">${qtyCell}</td>
                    <td class="text-end">${formatVND(line.price)}</td>
                    <td class="text-end">${formatVND(lineTotal)}</td>
                </tr>
            `;
        }).join('');
    } else {
        rows += `
            <tr>
                <td class="text-center">${stt++}</td>
                <td class="text-muted">Chưa có dịch vụ</td>
                <td class="text-center">0</td>
                <td class="text-end">0 đ</td>
                <td class="text-end">0 đ</td>
            </tr>
        `;
    }

    body.innerHTML = rows;
    totalEl.textContent = formatVND(total);
}

async function bdApplyLiveRoomPricing(detail) {
    bookingDetailRoomBreakdown = [];
    bookingDetailRoomFee = Number(detail.price || 0);

    if (detail.status !== 'checked_in' || !detail.room_number) {
        bookingDetailRoomLine.price = bookingDetailRoomFee;
        return;
    }

    try {
        const res = await fetch(api('/api/rooms/preview_checkout'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                number: detail.room_number,
                booking_id: detail.booking_id
            })
        });
        const data = await res.json();

        if (data.success) {
            bookingDetailRoomBreakdown = Array.isArray(data.bill_details) ? data.bill_details : [];
            bookingDetailRoomFee = Number((data.formatted_room_fee || '0').toString().replace(/\./g, '').replace(/[^0-9-]/g, ''));
            if (!bookingDetailRoomFee && data.bill_details) {
                bookingDetailRoomFee = data.bill_details.reduce((sum, x) => sum + Number(x.amount || 0), 0);
            }
            bookingDetailRoomLine.price = bookingDetailRoomFee;
        }
    } catch (err) {
        console.warn('Không lấy được đơn giá live cho booking detail:', err);
    }
}

function bdPrintInvoice() {
    const bookingCode = document.getElementById('bd-booking-code')?.textContent || '-';
    const customer = document.getElementById('bd-customer-label')?.textContent || '-';
    const room = document.getElementById('bd-room-title')?.textContent || '-';
    const checkIn = (document.getElementById('bd-checkin')?.value || '').replace('T', ' ');
    const checkOut = (document.getElementById('bd-checkout')?.value || '').replace('T', ' ');
    const total = document.getElementById('bd-invoice-total')?.textContent || '0 đ';
    const created = document.getElementById('bd-created-label')?.textContent || '-';
    const tableHtml = document.getElementById('bd-invoice-table-body')?.innerHTML || '';

    const printWin = window.open('', '_blank', 'width=900,height=700');
    if (!printWin) {
        alert('Trình duyệt đang chặn cửa sổ in. Vui lòng cho phép popup.');
        return;
    }

    const html = `
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Hoa don ${bookingCode}</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; color: #111; }
                h2 { margin: 0 0 8px; }
                .meta { margin-bottom: 12px; font-size: 14px; }
                .meta div { margin: 4px 0; }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                th, td { border: 1px solid #ccc; padding: 8px; font-size: 13px; }
                th { background: #f2f4f7; text-transform: uppercase; }
                .right { text-align: right; }
                .center { text-align: center; }
                .total { margin-top: 14px; text-align: right; font-size: 20px; font-weight: 700; color: #0f766e; }
            </style>
        </head>
        <body>
            <h2>HOA DON TAM TINH</h2>
            <div class="meta">
                <div><strong>Ma booking:</strong> ${bookingCode}</div>
                <div><strong>Khach hang:</strong> ${customer}</div>
                <div><strong>Phong:</strong> ${room}</div>
                <div><strong>Nhan phong:</strong> ${checkIn || '-'}</div>
                <div><strong>Tra phong:</strong> ${checkOut || '-'}</div>
                <div><strong>Tao luc:</strong> ${created}</div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 60px">STT</th>
                        <th>Hang muc</th>
                        <th style="width: 100px">So luong</th>
                        <th style="width: 140px">Don gia</th>
                        <th style="width: 140px">Thanh tien</th>
                    </tr>
                </thead>
                <tbody>${tableHtml}</tbody>
            </table>
            <div class="total">Tong tien: ${total}</div>
            <script>
                window.onload = function () { window.print(); };
            </script>
        </body>
        </html>
    `;

    printWin.document.open();
    printWin.document.write(html);
    printWin.document.close();
}

function bdUpdateServiceQty(index, value) {
    const qty = Math.max(1, parseInt(value || 1, 10));
    if (!bookingDetailServicesLines[index]) return;
    bookingDetailServicesLines[index].quantity = qty;
    renderBookingDetailServices();
}

function bdChangeServiceQty(index, delta) {
    if (!bookingDetailCanEditServices || !bookingDetailServicesLines[index]) return;
    const nextQty = Number(bookingDetailServicesLines[index].quantity || 0) + Number(delta || 0);
    if (nextQty <= 0) {
        bdRemoveServiceLine(index);
        return;
    }
    bookingDetailServicesLines[index].quantity = nextQty;
    renderBookingDetailServices();
}

function bdRemoveServiceLine(index) {
    if (!bookingDetailCanEditServices) return;
    bookingDetailServicesLines.splice(index, 1);
    renderBookingDetailServices();
}

function bdAddServiceById(serviceId, qty = 1) {
    if (!bookingDetailCanEditServices) return;

    const normalizedServiceId = parseInt(serviceId, 10);
    const normalizedQty = Math.max(1, parseInt(qty || 1, 10));
    const service = bookingDetailServicesCatalog.find(s => Number(s.id) === normalizedServiceId);

    if (!service) {
        alert('Không tìm thấy dịch vụ.');
        return;
    }

    const existing = bookingDetailServicesLines.find(x => Number(x.service_id) === normalizedServiceId);
    if (existing) {
        existing.quantity += normalizedQty;
    } else {
        bookingDetailServicesLines.push({
            service_id: service.id,
            name: service.name,
            price: Number(service.price || 0),
            quantity: normalizedQty,
        });
    }

    renderBookingDetailServices();
}

function focusServiceSidebar() {
    bdSwitchSidebarTab('services');
    const searchEl = document.getElementById('bd-service-search');
    if (searchEl) {
        searchEl.focus();
    }
}

function openGroupCheckoutFromDetail() {
    const bookingId = document.getElementById('bd-booking-id')?.value;
    if (!bookingId) {
        alert('Không xác định được booking đoàn.');
        return;
    }

    const detailModalEl = document.getElementById('bookingDetailModal');
    const detailModal = bootstrap.Modal.getInstance(detailModalEl);
    if (detailModal) {
        detailModal.hide();
    }

    if (typeof window.openGroupCheckout === 'function') {
        window.openGroupCheckout(bookingId);
    } else {
        alert('Không tìm thấy chức năng thanh toán đoàn.');
    }
}

function bdSwitchSidebarTab(tabName) {
    const servicesBtn = document.getElementById('bd-tab-services');
    const roomsBtn = document.getElementById('bd-tab-rooms');
    const servicesPane = document.getElementById('bd-sidebar-pane-services');
    const roomsPane = document.getElementById('bd-sidebar-pane-rooms');

    if (!servicesBtn || !roomsBtn || !servicesPane || !roomsPane) return;

    const target = tabName === 'rooms' ? 'rooms' : 'services';
    bookingDetailSidebarTab = target;

    servicesBtn.classList.toggle('active', target === 'services');
    roomsBtn.classList.toggle('active', target === 'rooms');
    servicesPane.classList.toggle('d-none', target !== 'services');
    roomsPane.classList.toggle('d-none', target !== 'rooms');
}

function renderBookingDetailRoomList(rooms, activeBookingRoomId) {
    const roomTabBtn = document.getElementById('bd-tab-rooms');
    const listEl = document.getElementById('bd-group-room-list');
    const countEl = document.getElementById('bd-group-room-count');

    if (!roomTabBtn || !listEl || !countEl) return;

    const roomRows = Array.isArray(rooms) ? rooms : [];
    countEl.textContent = String(roomRows.length || 0);

    if (roomRows.length <= 1) {
        roomTabBtn.classList.add('d-none');
        listEl.innerHTML = '';
        bdSwitchSidebarTab('services');
        return;
    }

    roomTabBtn.classList.remove('d-none');
    listEl.innerHTML = roomRows.map((r) => {
        const isActive = String(r.booking_room_id) === String(activeBookingRoomId);
        const itemClass = isActive ? 'list-group-item list-group-item-action active' : 'list-group-item list-group-item-action';
        const statusText = r.status || '--';
        const checkInText = r.check_in || '--';
        const depositText = formatVND(r.deposit || 0);

        return `
            <button type="button" class="${itemClass}" onclick="openBookingDetailModal(${Number(r.booking_room_id)})">
                <div class="d-flex justify-content-between align-items-center">
                    <strong>Phòng ${r.room_number || '---'}</strong>
                    <small>${statusText}</small>
                </div>
                <div class="small opacity-75">Nhận: ${checkInText}</div>
                <div class="small opacity-75">Cọc: ${depositText}</div>
            </button>
        `;
    }).join('');
}

function renderBookingRescheduleHistory(rows) {
    const container = document.getElementById('bd-reschedule-history');
    if (!container) return;
    container.replaceChildren();
    if (!rows || rows.length === 0) {
        container.classList.add('d-none');
        return;
    }

    container.className = 'mt-3 border rounded-3 bg-light p-3';
    const heading = document.createElement('h6');
    heading.className = 'fw-bold mb-2';
    heading.innerHTML = '<i class="fas fa-clock-rotate-left me-1 text-primary"></i>Lịch sử dời lịch';
    container.appendChild(heading);
    rows.forEach(row => {
        const item = document.createElement('div');
        item.className = 'border-top pt-2 mt-2 small';
        const priceLabel = row.price_mode === 'reprice' ? 'Áp dụng giá hiện tại' : 'Giữ giá đã chốt';
        item.textContent = `${row.created_at} · ${row.actor_name} · ${priceLabel}`;
        const schedule = document.createElement('div');
        schedule.className = 'text-muted mt-1';
        schedule.textContent = `Phòng ${row.old_room_id}: ${row.old_check_in} → ${row.old_check_out}  |  Phòng ${row.new_room_id}: ${row.new_check_in} → ${row.new_check_out}`;
        const reason = document.createElement('div');
        reason.className = 'mt-1';
        reason.textContent = `Lý do: ${row.reason}`;
        item.append(schedule, reason);
        container.appendChild(item);
    });
}

async function openBookingDetailModal() {
    let bookingRoomId = arguments.length > 0 ? arguments[0] : null;
    if (!bookingRoomId) {
        bookingRoomId = document.getElementById('bd-booking-room-id')?.value;
    }
    if (!bookingRoomId) {
        bookingRoomId = document.getElementById('edit-booking-room-id')?.value;
    }
    if (!bookingRoomId) {
        alert('Chưa có booking để xem chi tiết.');
        return;
    }

    try {
        const [detailRes, roomsRes, catalogRes] = await Promise.all([
            fetch(api('/api/bookings/' + bookingRoomId)),
            fetch(api('/api/rooms')),
            fetch(api('/api/bookings/services-catalog'))
        ]);

        const detail = await detailRes.json();
        const roomData = await roomsRes.json();
        const catalog = await catalogRes.json();

        if (detail.success === false) {
            alert(detail.msg || 'Không thể tải chi tiết booking.');
            return;
        }

        bookingDetailServicesCatalog = Array.isArray(catalog) ? catalog : [];
        bookingDetailServicesLines = Array.isArray(detail.room_services) ? detail.room_services.map(x => ({
            service_id: Number(x.service_id),
            name: x.name,
            price: Number(x.price || 0),
            quantity: Number(x.quantity || 0),
        })) : [];

        bookingDetailRoomLine = {
            name: `${detail.room_number || '---'} - ${(detail.rental_type === 'hourly' ? 'Theo giờ' : 'Theo ngày')}`,
            price: Number(detail.price || 0)
        };
        await bdApplyLiveRoomPricing(detail);

        document.getElementById('bd-booking-id').value = detail.booking_id || '';
        document.getElementById('bd-booking-room-id').value = detail.id || '';
        document.getElementById('bd-room-number').value = detail.room_number || '';
        document.getElementById('bd-booking-code').textContent = detail.booking_code || '';
        document.getElementById('bd-summary-code').value = detail.booking_code || '-';
        document.getElementById('bd-created-at').value = detail.created_at || '-';
        document.getElementById('bd-total-amount').value = Number(detail.booking_total_amount || 0);
        document.getElementById('bd-prepaid-amount').value = Number(detail.booking_prepaid_amount || 0);

        document.getElementById('bd-customer-name').value = detail.customer_name || '';
        document.getElementById('bd-customer-phone').value = detail.customer_phone || '';
        document.getElementById('bd-status').value = detail.status || 'booked';
        document.getElementById('bd-checkin').value = detail.check_in || '';
        document.getElementById('bd-checkout').value = detail.check_out || '';
        document.getElementById('bd-deposit').value = detail.deposit || 0;
        document.getElementById('bd-note').value = detail.note || '';
        document.getElementById('bd-rental-type').value = detail.rental_type || 'daily';

        document.getElementById('bd-room-title').textContent = detail.room_number || '---';
        document.getElementById('bd-room-name').textContent = (detail.rental_type === 'hourly' ? 'Theo giờ' : 'Theo ngày');
        document.getElementById('bd-customer-label').textContent = detail.customer_name || 'Khách lẻ';
        document.getElementById('bd-created-label').textContent = detail.created_at || '-';
        document.getElementById('bd-prepaid-label').textContent = formatVND(detail.booking_prepaid_amount || 0);
        renderBookingRescheduleHistory(detail.reschedules || []);

        const roomSelect = document.getElementById('bd-room-select');
        roomSelect.innerHTML = '';

        const bookingRooms = Array.isArray(detail.rooms) ? detail.rooms : [];
        const fallbackRooms = roomData.rooms || roomData || [];
        const hasBookingRoomOptions = bookingRooms.length > 0;

        renderBookingDetailRoomList(bookingRooms, detail.id);
        if (hasBookingRoomOptions) {
            bdSwitchSidebarTab('rooms');
        } else {
            bdSwitchSidebarTab('services');
        }

        if (bookingRooms.length > 0) {
            bookingRooms.forEach(r => {
                const statusLabel = r.status || '';
                roomSelect.innerHTML += `<option value="${r.booking_room_id}" data-room-id="${r.room_id}" data-room-number="${r.room_number}" title="${statusLabel}">${r.room_number}</option>`;
            });
            roomSelect.value = String(detail.id);
        } else {
            fallbackRooms.forEach(r => {
                const roomNumber = r.number || r.room_number;
                roomSelect.innerHTML += `<option value="${r.id}" data-room-id="${r.id}" data-room-number="${roomNumber}">${roomNumber}</option>`;
            });
            roomSelect.value = String(detail.room_id);
        }

        roomSelect.onchange = () => {
            const selectedBookingRoomId = roomSelect.value;
            if (hasBookingRoomOptions && selectedBookingRoomId && String(selectedBookingRoomId) !== String(detail.id)) {
                openBookingDetailModal(selectedBookingRoomId);
                return;
            }

            const selectedOption = roomSelect.options[roomSelect.selectedIndex];
            const selectedRoomNumber = selectedOption?.dataset?.roomNumber || detail.room_number;
            bookingDetailRoomLine.name = `${selectedRoomNumber || '---'} - ${(detail.rental_type === 'hourly' ? 'Theo giờ' : 'Theo ngày')}`;
            renderBookingDetailServices();
        };

        const canEditServices = detail.status === 'checked_in';
        bookingDetailCanEditServices = canEditServices;
        document.getElementById('bd-save-services-btn').disabled = !bookingDetailCanEditServices;
        const checkoutBtn = document.getElementById('bd-checkout-direct-btn');
        if (checkoutBtn) {
            checkoutBtn.disabled = !canEditServices;
        }

        const groupPayBtn = document.getElementById('bd-group-pay-btn');
        const isGroupBooking = Boolean(detail.is_group || Number(detail.room_count || 0) > 1);
        if (groupPayBtn) {
            groupPayBtn.style.display = (isGroupBooking && canEditServices) ? 'inline-block' : 'none';
        }

        const payNowBtn = document.getElementById('bd-pay-now-btn');
        if (payNowBtn) {
            payNowBtn.disabled = !canEditServices;
        }
        document.getElementById('bd-service-note').className = canEditServices
            ? 'alert alert-success py-2 px-2 small mb-0'
            : 'alert alert-warning py-2 px-2 small mb-0';
        document.getElementById('bd-service-note').textContent = canEditServices
            ? 'Phòng đang ở: có thể thêm/sửa dịch vụ và lưu ngay.'
            : 'Chỉ thêm/sửa dịch vụ khi phòng ở trạng thái Đang ở.';

        renderBookingDetailServiceCatalog();
        bdUpdateStayDuration();
        renderBookingDetailServices();

        const checkInEl = document.getElementById('bd-checkin');
        const checkOutEl = document.getElementById('bd-checkout');
        if (checkInEl) checkInEl.onchange = bdUpdateStayDuration;
        if (checkOutEl) checkOutEl.onchange = bdUpdateStayDuration;

        bootstrap.Modal.getOrCreateInstance(document.getElementById('bookingDetailModal')).show();
    } catch (err) {
        console.error(err);
        alert('Không tải được chi tiết booking.');
    }
}

function saveBookingChangesFromDetail() {
    const roomSelect = document.getElementById('bd-room-select');
    const selectedOption = roomSelect?.options?.[roomSelect.selectedIndex];
    const selectedRoomId = selectedOption?.dataset?.roomId || roomSelect?.value;

    const payload = {
        booking_id: document.getElementById('bd-booking-id').value,
        booking_room_id: document.getElementById('bd-booking-room-id').value,
        room_id: selectedRoomId,
        status: document.getElementById('bd-status').value,
        check_in: document.getElementById('bd-checkin').value,
        check_out: document.getElementById('bd-checkout').value,
        deposit: document.getElementById('bd-deposit').value,
    };

    fetch(api('/api/bookings/update'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            alert('Đã lưu thông tin booking.');
            bdUpdateStayDuration();
            loadTimeline();
        } else {
            alert(d.msg || 'Không lưu được booking.');
        }
    })
    .catch(err => alert('Lỗi kết nối: ' + err));
}

function saveBookingServicesFromDetail() {
    const status = document.getElementById('bd-status').value;
    if (status !== 'checked_in') {
        alert('Chỉ lưu dịch vụ khi phòng đang ở.');
        return;
    }

    const roomSelect = document.getElementById('bd-room-select');
    const selectedOption = roomSelect?.options?.[roomSelect.selectedIndex];
    const roomNumber = selectedOption?.dataset?.roomNumber || selectedOption?.text;
    if (!roomNumber) {
        alert('Không xác định được phòng để lưu dịch vụ.');
        return;
    }

    const servicesPayload = bookingDetailServicesLines
        .filter(x => Number(x.quantity || 0) > 0)
        .map(x => ({
            service_id: Number(x.service_id),
            quantity: Number(x.quantity),
        }));

    fetch(api('/api/bookings/update_services'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            number: roomNumber,
            booking_room_id: document.getElementById('bd-booking-room-id').value,
            services: servicesPayload,
        })
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            alert('Đã lưu dịch vụ cho phòng ' + roomNumber + '.');
            openBookingDetailModal();
            loadTimeline();
        } else {
            alert(d.msg || 'Không lưu được dịch vụ.');
        }
    })
    .catch(err => alert('Lỗi kết nối: ' + err));
}

// ========================================================
// 4. CHỨC NĂNG THÊM PHÒNG VÀO ĐOÀN (NEW)
// ========================================================
function addRoomToExistingBooking() {
    const bookingId = document.getElementById('edit-booking-id').value;
    if (!bookingId) { alert("Không tìm thấy mã đoàn!"); return; }

    const roomNumber = prompt("Nhập số phòng muốn lấy thêm cho đoàn này:");
    if (!roomNumber) return;

    // Lấy ngày giờ từ form hiện tại làm mặc định
    const checkIn = document.getElementById('edit-checkin').value;
    const checkOut = document.getElementById('edit-checkout').value;

    fetch(api('/api/bookings/add-room'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            booking_id: bookingId,
            room_number: roomNumber,
            check_in: checkIn,
            check_out: checkOut
        })
    })
    .then(r => r.json())
    .then(d => {
        if(d.success) {
            alert(d.msg);
            bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();
            loadTimeline();
        } else {
            alert("Lỗi: " + d.msg);
        }
    });
}

// ========================================================
// 5. LOGIC TÍNH TOÁN HOÀN TIỀN
// ========================================================
function toggleRefundSection() {
    const status = document.getElementById('edit-status').value;
    const section = document.getElementById('refund-section');
    if (!section) return;
    section.style.display = (status === 'cancelled') ? 'block' : 'none';
}

// ========================================================
// HÀM TÍNH TỰ ĐỘNG TIỀN CỌC QUA API (HỖ TRỢ TRUYỀN TỶ LỆ)
// ========================================================
// Mặc định gọi hàm không truyền gì thì tính 50% (dùng cho onchange ngày/giờ)
// ========================================================
// HÀM TÍNH TỰ ĐỘNG TIỀN PHÒNG & TIỀN CỌC
// (Đã bỏ yêu cầu cọc đối với khách thuê theo giờ)
// ========================================================
async function calculateQuickDeposit(percent = 0.5) {
    const rentalType = document.getElementById('bk-type').value; // 'daily' hoặc 'hourly'
    const checkInVal = rentalType === 'daily' ? document.getElementById('bk-daily-in').value : document.getElementById('bk-hourly-in').value;
    const checkOutVal = rentalType === 'daily' ? document.getElementById('bk-daily-out').value : document.getElementById('bk-hourly-out').value;
    const roomId = document.getElementById('bk-room-id').value;
    const depositInput = document.getElementById('bk-deposit');
    const hintText = document.getElementById('deposit-hint');

    // Chờ người dùng chọn đủ phòng và thời gian mới tính
    if (!checkInVal || !checkOutVal || !roomId) {
        if (hintText) hintText.innerText = "Vui lòng chọn thời gian để tính giá.";
        return;
    }

    const checkIn = new Date(checkInVal);
    const checkOut = new Date(checkOutVal);

    if (checkOut - checkIn <= 0) {
        if (hintText) hintText.innerText = "⚠️ Giờ Check-out phải sau Check-in!";
        return;
    }

    if (hintText) hintText.innerText = "⏳ Đang tính toán giá theo hệ thống...";

    try {
        // Gọi API backend để lấy tổng tiền phòng
        const response = await fetch(api('/api/bookings/calculate-price'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                room_id: roomId,
                check_in: checkInVal,
                check_out: checkOutVal,
                rental_type: rentalType
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentBookingQuote = data.quote || null;
            const totalAmount = Number(data.quote?.total || data.total_amount);
            const optionKey = percent === 1 ? 'maximum_100' : 'suggested_50';
            const suggestedDeposit = Number(
                data.quote?.deposit_options?.[optionKey] ?? totalAmount * percent
            );
            const percentLabel = percent === 1 ? "100%" : "50%";
            selectedDepositRatio = percent;

            if (depositInput) depositInput.value = suggestedDeposit;

            if (hintText) {
                hintText.innerHTML = `<span class="text-success fw-bold">Đã chọn cọc (${percentLabel}): ${suggestedDeposit.toLocaleString('vi-VN')} đ</span> <br> (Tổng tiền phòng tạm tính: ${totalAmount.toLocaleString('vi-VN')} đ)`;
            }
        } else {
            if (hintText) hintText.innerText = `⚠️ Lỗi từ hệ thống tính giá: ${data.msg}`;
        }
    } catch (err) {
        console.error("Lỗi tính giá:", err);
        if (hintText) hintText.innerText = "⚠️ Không thể kết nối đến máy chủ để tính giá.";
    }
}

// ========================================================
// 6. HELPER FUNCTIONS
// ========================================================
function performCheckInFromTimeline() {
    const bookingRoomId = document.getElementById('edit-booking-room-id').value;
    const bookingId = document.getElementById('edit-booking-id').value;
    const select = document.getElementById('edit-room-select');
    const roomNumber = select.options[select.selectedIndex].text;

    if (!confirm(`Xác nhận nhận phòng ${roomNumber} cho khách?`)) return;

    fetch(api('/api/rooms/checkin'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
            booking_room_id: parseInt(bookingRoomId)
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.msg);
            bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();
            loadTimeline(); // Load lại timeline để cập nhật màu sắc
        } else {
            alert("Lỗi: " + data.msg);
        }
    })
    .catch(err => alert("Lỗi kết nối: " + err));
}

function openCheckoutFromTimeline() {
    // Truyền cả ID đoàn và tên phòng
    const bookingId = document.getElementById('bd-booking-id')?.value || document.getElementById('edit-booking-id').value;

    let roomNumber = '';
    const detailSelect = document.getElementById('bd-room-select');
    if (detailSelect && detailSelect.selectedIndex >= 0) {
        const selectedOption = detailSelect.options[detailSelect.selectedIndex];
        roomNumber = selectedOption?.dataset?.roomNumber || selectedOption?.text || '';
    }

    if (!roomNumber) {
        const select = document.getElementById('edit-room-select');
        if (select && select.selectedIndex >= 0) {
            roomNumber = select.options[select.selectedIndex].text;
        }
    }

    if (!roomNumber) {
        alert('Không xác định được phòng để thanh toán.');
        return;
    }

    const editModal = bootstrap.Modal.getInstance(document.getElementById('editBookingModal'));
    if (editModal) editModal.hide();
    const detailModal = bootstrap.Modal.getInstance(document.getElementById('bookingDetailModal'));
    if (detailModal) detailModal.hide();

    const checkoutFn = window.checkOut;
    if (typeof checkoutFn === 'function') {
        checkoutFn(roomNumber, bookingId);
    } else {
        alert("Lỗi: Không tìm thấy hàm checkOut().");
    }
}

function setRentalType(type) {
    document.getElementById('bk-type').value = type;
}

function updateHourlyEnd() {
    let startStr = document.getElementById('bk-hourly-in').value;
    if(!startStr) return;
    let start = new Date(startStr);
    start.setHours(start.getHours() + 2); 
    document.getElementById('bk-hourly-out').value = toLocalISO(start);
}

function toLocalISO(date) {
    var local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
}

// Đợi giao diện HTML load xong thì mới gắn sự kiện
document.addEventListener('DOMContentLoaded', function() {
    
    const typeSelect = document.getElementById('bk-type');
    
    // Kiểm tra xem thẻ có tồn tại không rồi mới gắn sự kiện
    if (typeSelect) {
        typeSelect.addEventListener('change', function() {
            const quickDepositButtons = document.getElementById('quick-deposit-buttons');
            const depositInput = document.getElementById('bk-deposit');
            const hintText = document.getElementById('deposit-hint');
            
            selectedDepositRatio = null;
            currentBookingQuote = null;

            // Luôn hiện nút cọc nhanh để bắt buộc chọn 50% hoặc 100%.
            if (quickDepositButtons) {
                quickDepositButtons.style.display = 'block';
            }
            
            if (depositInput) {
                depositInput.value = 0;
            }

            if (hintText) {
                hintText.innerText = 'Vui lòng bấm nút cọc 50% hoặc 100% trước khi tạo booking.';
            }
            
        });
    }

    const depositInput = document.getElementById('bk-deposit');
    if (depositInput) {
        depositInput.addEventListener('input', function() {
            selectedDepositRatio = null;
            currentBookingQuote = null;
        });
    }

});

// --- TÍNH NĂNG NHẬN DIỆN KHÁCH CŨ QUA SĐT (BOOKING LẺ) ---
document.addEventListener('DOMContentLoaded', function() {
    const phoneInput = document.getElementById('bk-phone');
    const nameInput = document.getElementById('bk-name');
    let debounceTimer;

    if (phoneInput && nameInput) {
        phoneInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            const customerIdInput = document.getElementById('bk-customer-id');
            const candidateContainer = document.getElementById('bk-customer-candidates');
            if (customerIdInput) customerIdInput.value = '';
            if (candidateContainer) {
                candidateContainer.classList.add('d-none');
                candidateContainer.replaceChildren();
            }
            const phone = this.value.trim();
            if (phone.length < 4) return;

            debounceTimer = setTimeout(() => {
                fetch(api(`/api/customers?q=${phone}`))
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
});
