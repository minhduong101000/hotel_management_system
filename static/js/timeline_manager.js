// static/js/timeline_manager.js

var timeline;
var roomMap = {}; // Dùng để map ID phòng -> Số phòng

document.addEventListener('DOMContentLoaded', () => {
    loadTimeline();
});

// ========================================================
// 1. LOAD TIMELINE (VIS.JS)
// ========================================================
function loadTimeline() {
    fetch('/api/bookings/timeline')
        .then(res => res.json())
        .then(data => {
            // Lưu map để dùng khi click tạo mới
            if (data.groups) {
                data.groups.forEach(g => {
                    roomMap[g.id] = g.room_number || g.content;
                });
            }

            var container = document.getElementById('visualization');
            
            // QUAN TRỌNG: Khai báo items ra biến để dùng trong sự kiện click
            var items = new vis.DataSet(data.items);
            var groups = new vis.DataSet(data.groups);

            var options = {
                groupOrder: 'content', 
                orientation: 'top',
                stack: true, 
                zoomKey: 'ctrlKey', 
                minHeight: '550px',
                start: new Date(new Date().getTime() - 24 * 60 * 60 * 1000), 
                end: new Date(new Date().getTime() + 3 * 24 * 60 * 60 * 1000), 
                locale: 'vi', 
                tooltip: {
                    followMouse: true,
                    overflowMethod: 'cap'
                }
            };

            if (timeline) timeline.destroy();
            timeline = new vis.Timeline(container, items, groups, options);

            // BẮT SỰ KIỆN CLICK
            timeline.on('click', function (properties) {
                if (properties.item) {
                    // --- SỬA LOGIC LẤY DATA TẠI ĐÂY ---
                    // Lấy toàn bộ data của item (bao gồm booking_id mà backend trả về)
                    var itemData = items.get(properties.item);
                    
                    if (itemData) {
                        // itemData.id = ID của BookingRoom (Chi tiết phòng)
                        // itemData.booking_id = ID của Booking (Đoàn/Tổng)
                        openEditModal(itemData.id, itemData.booking_id);
                    }
                } else if (properties.what === 'background' && properties.group) {
                    // Click vào ô trống -> Mở Modal Tạo mới
                    openCreateModal(properties.group, properties.time);
                }
            });
        })
        .catch(err => console.error("Lỗi tải timeline:", err));
}

// ========================================================
// 2. MODAL TẠO MỚI (CREATE)
// ========================================================
function openCreateModal(roomId, time) {
    document.getElementById('bk-room-number').innerText = roomMap[roomId] || '...';
    document.getElementById('booking-form').reset();

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
    
    new bootstrap.Modal(document.getElementById('bookingModal')).show();
}

function submitFullBooking(status) {
    const rentalType = document.getElementById('bk-type').value;
    
    const data = {
        room_number: document.getElementById('bk-room-number').innerText,
        phone: document.getElementById('bk-phone').value,
        name: document.getElementById('bk-name').value,
        rental_type: rentalType,
        status: status, 
        check_in: rentalType === 'daily' ? document.getElementById('bk-daily-in').value : document.getElementById('bk-hourly-in').value,
        check_out: rentalType === 'daily' ? document.getElementById('bk-daily-out').value : document.getElementById('bk-hourly-out').value,
        deposit: document.getElementById('bk-deposit').value,
        note: document.getElementById('bk-note').value
    };

    if(!data.phone) { alert("Vui lòng nhập Số điện thoại khách!"); return; }

    fetch('/api/bookings/create', {
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
            alert(d.msg);
        }
    })
    .catch(err => alert("Lỗi kết nối: " + err));
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
    fetch('/api/rooms').then(r => r.json()).then(rData => {
        const sel = document.getElementById('edit-room-select');
        sel.innerHTML = '';
        let rooms = rData.rooms || rData; 
        rooms.forEach(r => {
            sel.innerHTML += `<option value="${r.id}">${r.number || r.room_number}</option>`;
        });

        // Bước 2: Lấy chi tiết BookingRoom (để điền giờ cụ thể của phòng này)
        // Lưu ý: API này cần trả về thông tin của dòng BookingRoomId
        return fetch('/api/bookings/' + bookingRoomId); 
    }).then(r => r.json()).then(data => {
        
        // Điền dữ liệu vào form
        document.getElementById('edit-id').innerText = data.booking_id; // Hiển thị mã đoàn
        document.getElementById('edit-customer').value = data.customer_name;
        document.getElementById('edit-room-select').value = data.room_id;
        document.getElementById('edit-status').value = data.status;

        // Giờ check-in/out của RIÊNG phòng này
        document.getElementById('edit-checkin').value = data.check_in;
        document.getElementById('edit-checkout').value = data.check_out;
        
        // Tiền cọc (thường gắn với Booking tổng, nhưng hiển thị ở đây để sửa)
        document.getElementById('edit-deposit').value = data.deposit;
        
        // Reset giao diện hoàn tiền
        const chkForce = document.getElementById('chk-force-majeure');
        if(chkForce) chkForce.checked = false;
        
        toggleRefundSection();

        new bootstrap.Modal(document.getElementById('editBookingModal')).show();
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

        const chkForce = document.getElementById('chk-force-majeure');
        const isForceMajeure = chkForce ? chkForce.checked : false;

        fetch('/api/bookings/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                booking_room_id: bookingRoomId, // Gửi ID phòng để hủy đúng phòng
                booking_id: bookingId,          // Fallback
                is_force_majeure: isForceMajeure
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
            deposit: document.getElementById('edit-deposit').value
        };

        fetch('/api/bookings/update', {
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

    fetch('/api/bookings/add-room', {
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
    
    if (status === 'cancelled') {
        section.style.display = 'block';
        calculateRefund(); 
    } else {
        section.style.display = 'none';
        document.getElementById('refund-amount-value').value = 0;
    }
}

function calculateRefund() {
    const depositVal = document.getElementById('edit-deposit').value || 0;
    const deposit = parseFloat(depositVal);
    const chkForce = document.getElementById('chk-force-majeure');
    const selPercent = document.getElementById('refund-percent');
    
    let percent = 0;
    if (chkForce && chkForce.checked) {
        percent = 100;
        selPercent.value = "100";
        selPercent.disabled = true;
    } else {
        percent = parseInt(selPercent.value);
        selPercent.disabled = false;
    }

    const refund = deposit * (percent / 100);
    document.getElementById('refund-final-text').innerText = refund.toLocaleString('vi-VN') + ' đ';
    document.getElementById('refund-amount-value').value = refund;
}

// ========================================================
// 6. HELPER FUNCTIONS
// ========================================================
function openCheckoutFromTimeline() {
    // Truyền cả ID đoàn và tên phòng
    const bookingId = document.getElementById('edit-booking-id').value;
    const select = document.getElementById('edit-room-select');
    const roomNumber = select.options[select.selectedIndex].text; 

    bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();

    if (typeof checkOut === 'function') {
        checkOut(roomNumber, bookingId);
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