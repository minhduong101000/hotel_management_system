document.addEventListener('DOMContentLoaded', () => {
    loadData();
});

async function loadData() {
    try {
        const res = await fetch('/api/timeline-data');
        if (res.status === 401) window.location.href = '/login'; // Chưa login -> Đá về login
        
        const json = await res.json();
        if (json.status === 'success') {
            renderTimeline(json.data);
        } else {
            console.error(json.message);
        }
    } catch (e) { console.error(e); }
}

function renderTimeline(data) {
    const { rooms, bookings, start_date } = data;
    const tbody = document.getElementById('timeline-body');
    const thead = document.getElementById('timeline-header');
    
    tbody.innerHTML = '';
    // Thêm class align-middle để căn giữa chiều dọc
    thead.innerHTML = '<th class="sticky-col py-3 ps-4 text-start" style="width:150px; border-top-left-radius: 12px;">PHÒNG</th>';

    // 1. Render Header
    for (let i = 0; i < 14; i++) {
        let d = new Date(start_date);
        d.setDate(d.getDate() + i);
        
        let dayName = d.toLocaleDateString('vi-VN', { weekday: 'short' });
        let dateNum = d.getDate();
        
        // Highlight cuối tuần
        let isWeekend = (d.getDay() === 0 || d.getDay() === 6);
        let colorStyle = isWeekend ? 'color: var(--primary-color);' : '';
        let bgStyle = isWeekend ? 'background-color: #eef2ff;' : '';

        thead.innerHTML += `
            <th class="text-center py-3" style="${bgStyle}">
                <div style="font-size: 1.2rem; font-weight: 700; ${colorStyle}">${dateNum}</div>
                <div style="font-size: 0.65rem; font-weight: 500; opacity: 0.7;">${dayName}</div>
            </th>`;
    }

    // 2. Render Body
    rooms.forEach(room => {
        // Cột tên phòng đẹp hơn
        let rowHtml = `
            <tr>
                <td class="sticky-col ps-4 py-3 bg-white">
                    <div class="d-flex align-items-center">
                        <div class="bg-light text-primary rounded-circle d-flex align-items-center justify-content-center me-2" style="width: 32px; height: 32px; font-weight:bold;">
                            ${room.number.substring(0,1)}
                        </div>
                        <div>
                            <div class="fw-bold text-dark">${room.number}</div>
                            <div class="text-muted" style="font-size: 10px;">${room.type}</div>
                        </div>
                    </div>
                </td>`;
        
        for (let i = 0; i < 14; i++) {
            let currentStr = new Date(start_date);
            currentStr.setDate(currentStr.getDate() + i);
            let dateStr = currentStr.toISOString().split('T')[0];

            const booking = bookings.find(b => 
                b.room_id === room.id && 
                dateStr >= b.check_in && 
                dateStr < b.check_out
            );

            // Ô dữ liệu
            rowHtml += '<td class="p-1 align-middle text-center">';
            
            if (booking) {
                // Hiển thị dạng viên thuốc (Pill)
                rowHtml += `
                    <div class="booking-pill w-100" title="${booking.customer_name}">
                        <div class="text-truncate" style="max-width: 80px;">${booking.customer_name}</div>
                    </div>`;
            } else {
                // Ô trống có icon dấu cộng mờ
                rowHtml += `
                    <div class="empty-slot d-flex align-items-center justify-content-center" 
                         onclick="openModal('${room.number}', '${dateStr}')">
                        <i class="fas fa-plus fa-xs"></i>
                    </div>`;
            }
            rowHtml += '</td>';
        }
        rowHtml += `</tr>`;
        tbody.insertAdjacentHTML('beforeend', rowHtml);
    });
}

function adminAction() {
    fetch('/api/admin/reset-prices', {method:'POST'})
    .then(r => {
        if(r.status === 403) alert('Bạn là Staff, không có quyền Admin!');
        else alert('Đã thực hiện lệnh Admin!');
    });
}