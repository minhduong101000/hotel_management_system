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
            var items = new vis.DataSet(data.items);
            var groups = new vis.DataSet(data.groups);

            var options = {
                groupOrder: 'content', // Sắp xếp theo tên phòng
                orientation: 'top',
                stack: true, // Cho phép xếp chồng nếu trùng giờ
                zoomKey: 'ctrlKey', // Giữ Ctrl + lăn chuột để zoom
                minHeight: '550px',
                start: new Date(new Date().getTime() - 24 * 60 * 60 * 1000), // Nhìn từ hôm qua
                end: new Date(new Date().getTime() + 3 * 24 * 60 * 60 * 1000), // Đến 3 ngày tới
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
                    // Click vào booking -> Mở Modal Sửa
                    openEditModal(properties.item);
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
    // Điền số phòng
    document.getElementById('bk-room-number').innerText = roomMap[roomId] || '...';
    
    // Reset form
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

    // Mặc định chọn tab Theo Ngày
    setRentalType('daily');
    
    // Reset active tab UI (Bootstrap 5)
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
        status: status, // 'confirmed' hoặc 'checked_in'
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
            loadTimeline(); // Load lại timeline
        } else {
            alert(d.msg);
        }
    })
    .catch(err => alert("Lỗi kết nối: " + err));
}

// ========================================================
// 3. MODAL CHỈNH SỬA (EDIT) & LƯU THAY ĐỔI
// ========================================================
function openEditModal(bookingId) {
    // Bước 1: Load danh sách phòng để điền vào Select Box
    fetch('/api/rooms').then(r => r.json()).then(rData => {
        const sel = document.getElementById('edit-room-select');
        sel.innerHTML = '';
        
        let rooms = rData.rooms || rData; 
        rooms.forEach(r => {
            sel.innerHTML += `<option value="${r.id}">${r.number || r.room_number}</option>`;
        });

        // Bước 2: Lấy chi tiết Booking
        return fetch('/api/bookings/' + bookingId);
    }).then(r => r.json()).then(data => {
        // Điền dữ liệu vào form
        document.getElementById('edit-booking-id').value = data.id;
        document.getElementById('edit-id').innerText = data.id;
        document.getElementById('edit-customer').value = data.customer_name;
        document.getElementById('edit-room-select').value = data.room_id;
        
        // Cập nhật trạng thái
        const statusSelect = document.getElementById('edit-status');
        statusSelect.value = data.status;
        
        document.getElementById('edit-checkin').value = data.check_in;
        document.getElementById('edit-checkout').value = data.check_out;
        document.getElementById('edit-deposit').value = data.deposit;
        
        // --- XỬ LÝ GIAO DIỆN HOÀN TIỀN ---
        // 1. Reset checkbox Bất khả kháng
        const chkForce = document.getElementById('chk-force-majeure');
        if(chkForce) chkForce.checked = false;

        // 2. Reset dropdown % (Mở khóa và set về 50%)
        const refundSelect = document.getElementById('refund-percent');
        if(refundSelect) {
            refundSelect.disabled = false;
            refundSelect.value = "50";
        }

        // 3. Hiển thị/Ẩn section hoàn tiền dựa trên trạng thái hiện tại
        toggleRefundSection();

        new bootstrap.Modal(document.getElementById('editBookingModal')).show();
    })
    .catch(err => console.error(err));
}

function saveBookingChanges() {
    const bookingId = document.getElementById('edit-booking-id').value;
    const status = document.getElementById('edit-status').value;

    if (!bookingId) return;

    // --- TRƯỜNG HỢP 1: HỦY PHÒNG ---
    if (status === 'cancelled') {
        if (!confirm("Bạn có chắc chắn muốn HỦY đơn đặt phòng này không?")) return;

        // Kiểm tra xem có tick Bất khả kháng không
        const chkForce = document.getElementById('chk-force-majeure');
        const isForceMajeure = chkForce ? chkForce.checked : false;

        fetch('/api/bookings/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                booking_id: bookingId,
                is_force_majeure: isForceMajeure
            })
        })
        .then(r => r.json())
        .then(d => {
            if(d.success) {
                alert(d.msg); // Thông báo tiền hoàn
                bootstrap.Modal.getInstance(document.getElementById('editBookingModal')).hide();
                loadTimeline();
            } else {
                alert(d.msg);
            }
        })
        .catch(err => alert("Lỗi server: " + err));
    } 
    // --- TRƯỜNG HỢP 2: CẬP NHẬT THÔNG TIN ---
    else {
        const data = {
            booking_id: bookingId,
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
        })
        .catch(err => alert("Lỗi server: " + err));
    }
}

// ========================================================
// 4. LOGIC TÍNH TOÁN HOÀN TIỀN (REFUND)
// ========================================================
function toggleRefundSection() {
    const status = document.getElementById('edit-status').value;
    const section = document.getElementById('refund-section');
    
    // Chỉ hiện khi chọn Cancelled
    if (status === 'cancelled') {
        section.style.display = 'block';
        calculateRefund(); // Tính toán ngay lập tức
    } else {
        section.style.display = 'none';
        document.getElementById('refund-amount-value').value = 0;
    }
}

function calculateRefund() {
    // 1. Lấy tiền cọc
    const depositVal = document.getElementById('edit-deposit').value || 0;
    const deposit = parseFloat(depositVal);

    // 2. Kiểm tra Checkbox Bất khả kháng
    const chkForce = document.getElementById('chk-force-majeure');
    const selPercent = document.getElementById('refund-percent');
    
    let percent = 0;

    if (chkForce && chkForce.checked) {
        // Nếu chọn Bất khả kháng: Set 100% và KHÓA dropdown
        percent = 100;
        selPercent.value = "100";
        selPercent.disabled = true;
    } else {
        // Nếu không chọn: MỞ dropdown và lấy giá trị đang chọn
        percent = parseInt(selPercent.value);
        selPercent.disabled = false;
    }

    // 3. Tính tiền
    const refund = deposit * (percent / 100);

    // 4. Hiển thị text (Format tiền Việt)
    document.getElementById('refund-final-text').innerText = refund.toLocaleString('vi-VN') + ' đ';
    
    // 5. Lưu vào input ẩn
    document.getElementById('refund-amount-value').value = refund;
}

// ========================================================
// 5. CHUYỂN SANG THANH TOÁN (CHECKOUT BRIDGE) - UPDATE
// ========================================================
function openCheckoutFromTimeline() {
    // 1. Lấy ID booking từ input hidden
    const bookingId = document.getElementById('edit-booking-id').value;
    
    // 2. Lấy số phòng từ select box (để hiển thị hoặc fallback)
    const select = document.getElementById('edit-room-select');
    const roomNumber = select.options[select.selectedIndex].text; 

    // 3. Ẩn Modal Sửa
    const modalEl = document.getElementById('editBookingModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if(modal) modal.hide();

    // 4. Gọi hàm checkOut() bên file checkout.js
    // LƯU Ý: Hàm checkOut bên kia phải nhận 2 tham số: (roomNumber, bookingId)
    if (typeof checkOut === 'function') {
        checkOut(roomNumber, bookingId);
    } else {
        alert("Lỗi: Không tìm thấy hàm checkOut(). Vui lòng kiểm tra lại file checkout.js!");
    }
}

// ========================================================
// HELPER FUNCTIONS
// ========================================================
function setRentalType(type) {
    document.getElementById('bk-type').value = type;
}

function updateHourlyEnd() {
    let startStr = document.getElementById('bk-hourly-in').value;
    if(!startStr) return;
    let start = new Date(startStr);
    start.setHours(start.getHours() + 2); // Mặc định +2h
    document.getElementById('bk-hourly-out').value = toLocalISO(start);
}

// Format ngày giờ chuẩn ISO (YYYY-MM-DDTHH:mm) cho input HTML
function toLocalISO(date) {
    var local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
}