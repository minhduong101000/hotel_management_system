/**
 * static/js/price_manager.js
 * Phiên bản cập nhật: Hỗ trợ cấu hình giá giờ chi tiết (Block đầu + Giờ tiếp theo)
 */

let allRules = [];

document.addEventListener('DOMContentLoaded', () => {
    loadData();
});

// ========================================================
// 1. TẢI DỮ LIỆU
// ========================================================
function loadData() {
    fetch('/api/prices/all-data')
        .then(res => res.json())
        .then(data => {
            if (data.error) { alert(data.error); return; }
            
            allRules = data.rules; // Lưu biến toàn cục
            renderBaseTable(data.rooms);
            renderRulesTable(data.rules);
        })
        .catch(err => console.error("Lỗi tải dữ liệu:", err));
}

// ========================================================
// 2. VẼ BẢNG GIÁ BASE (CẬP NHẬT GIAO DIỆN 2 Ô GIÁ GIỜ)
// ========================================================
function renderBaseTable(rooms) {
    const tbody = document.getElementById('base-price-table');
    tbody.innerHTML = '';
    
    rooms.forEach(r => {
        // Xử lý null thành 0
        const pDaily = r.price_daily || 0;
        const pInit = r.price_initial || 0; // Key khớp với API backend
        const pNext = r.price_next || 0;    // Key khớp với API backend

        const tr = document.createElement('tr');
        tr.className = "align-middle"; // Căn giữa theo chiều dọc
        
        tr.innerHTML = `
            <td class="ps-3">
                <div class="fw-bold text-dark" style="font-size:1.1rem">P.${r.number}</div>
                <span class="badge bg-light text-secondary border">${r.type}</span>
            </td>
            
            <td>
                <div class="input-group input-group-sm">
                    <input type="number" class="form-control fw-bold text-success" 
                           id="base-d-${r.id}" value="${pDaily}" step="10000">
                    <span class="input-group-text">đ</span>
                </div>
            </td>
            
            <td>
                <div class="d-flex flex-column gap-1">
                    <div class="input-group input-group-sm" title="Giá cho block giờ đầu">
                        <span class="input-group-text bg-light text-primary fw-bold" style="width: 50px;">Đầu</span>
                        <input type="number" class="form-control" id="base-init-${r.id}" value="${pInit}">
                    </div>
                    <div class="input-group input-group-sm" title="Giá cho mỗi giờ tiếp theo">
                        <span class="input-group-text bg-light text-secondary" style="width: 50px;">Tiếp</span>
                        <input type="number" class="form-control" id="base-next-${r.id}" value="${pNext}">
                    </div>
                </div>
            </td>
            
            <td class="text-end pe-3">
                <button class="btn btn-sm btn-outline-primary border-0 rounded-circle p-2" 
                        onclick="updateBase(${r.id})" title="Lưu lại">
                    <i class="fas fa-save fa-lg"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// ========================================================
// 3. VẼ BẢNG LUẬT (BỎ HIỂN THỊ GIÁ GIỜ)
// ========================================================
function renderRulesTable(rules) {
    const tbody = document.getElementById('rules-table');
    tbody.innerHTML = '';
    
    if(rules.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4 small fst-italic">Chưa có luật giá nào.</td></tr>`;
        return;
    }

    rules.forEach(r => {
        // ... (Giữ nguyên logic format thời gian, badge, thứ...) ...
        // Format hiển thị thời gian
        let timeTxt = '<span class="badge bg-light text-dark border fw-normal">Cả năm</span>';
        if(r.start_date) {
            const dStart = r.start_date;
            const dEnd = r.end_date;
            timeTxt = `<span class="small fw-bold text-primary">${dStart} ➝ ${dEnd}</span>`;
        }
        
        // Format hiển thị thứ
        let dayTxt = '';
        if(r.days_of_week) {
            const mapDay = {'0':'T2','1':'T3','2':'T4','3':'T5','4':'T6','5':'T7','6':'CN'};
            const daysArr = r.days_of_week.split(',');
            const isWeekend = daysArr.every(d => d === '5' || d === '6');
            const color = isWeekend ? 'bg-danger' : 'bg-secondary';
            dayTxt = daysArr.map(d => `<span class="badge ${color} me-1" style="font-size: 0.65rem;">${mapDay[d]}</span>`).join('');
            dayTxt = `<div class="mt-1">${dayTxt}</div>`;
        } else if(!r.start_date) {
            dayTxt = '<div class="small text-muted mt-1">Tất cả ngày</div>';
        }

        let badge = r.priority == 2 
            ? '<span class="badge bg-warning text-dark ms-1" style="font-size: 0.6rem;">ƯU TIÊN</span>' 
            : '';

        const fmtDaily = formatCurrency(r.price_daily);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="ps-3">
                <div class="fw-bold text-dark">${r.name}</div>
                <span class="badge bg-light text-dark border">${r.room_type}</span> ${badge}
            </td>
            <td>
                ${timeTxt}
                ${dayTxt}
            </td>
            <td>
                <div class="fw-bold text-success">${fmtDaily}</div>
            </td>
            <td class="text-end pe-3">
                <button class="btn btn-sm text-primary" onclick="editRule(${r.id})"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm text-danger" onclick="deleteRule(${r.id})"><i class="fas fa-trash"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}
// ========================================================
// 4. LOGIC UPDATE BASE PRICE (GỬI 3 LOẠI GIÁ)
// ========================================================
function updateBase(id) {
    const daily = document.getElementById(`base-d-${id}`).value;
    const initial = document.getElementById(`base-init-${id}`).value;
    const next = document.getElementById(`base-next-${id}`).value;
    
    // Gửi JSON khớp với API backend đã sửa
    fetch('/api/prices/update-base', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
            id: id, 
            price_daily: daily, 
            price_initial: initial, 
            price_next: next 
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            // Visual feedback (đổi màu nút save)
            const btn = document.querySelector(`button[onclick="updateBase(${id})"]`);
            const icon = btn.querySelector('i');
            
            btn.classList.replace('btn-outline-primary', 'btn-success');
            icon.className = 'fas fa-check';
            
            setTimeout(() => {
                btn.classList.replace('btn-success', 'btn-outline-primary');
                icon.className = 'fas fa-save fa-lg';
            }, 1000);
        } else {
            alert(data.msg);
        }
    });
}

// ========================================================
// 5. CÁC HÀM MODAL RULE (SỬA LẠI LOGIC FILL DATA & SAVE)
// ========================================================
function openRuleModal() {
    document.getElementById('r-id').value = '';
    document.getElementById('rule-form').reset();
    document.querySelectorAll('input[name="daycheck"]').forEach(cb => cb.checked = true);
    document.querySelector('#ruleModal .modal-title').innerHTML = '<i class="fas fa-plus-circle me-2"></i>THÊM GIÁ MỚI';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).show();
}

function editRule(id) {
    const rule = allRules.find(r => r.id === id);
    if (!rule) return;
    
    document.getElementById('r-id').value = rule.id;
    document.getElementById('r-name').value = rule.name;
    document.getElementById('r-room-type').value = rule.room_type;
    document.getElementById('r-priority').value = rule.priority;
    document.getElementById('r-start').value = rule.start_date || '';
    document.getElementById('r-end').value = rule.end_date || '';
    
    // Chỉ fill giá ngày, KHÔNG CẦN fill giá giờ nữa vì input đã xóa
    document.getElementById('r-price-daily').value = rule.price_daily;
    
    // Checkbox logic giữ nguyên
    document.querySelectorAll('input[name="daycheck"]').forEach(cb => cb.checked = false);
    if(rule.days_of_week) {
        const arr = rule.days_of_week.split(',');
        document.querySelectorAll('input[name="daycheck"]').forEach(cb => {
            if(arr.includes(cb.value)) cb.checked = true;
        });
    }
    
    document.querySelector('#ruleModal .modal-title').innerHTML = `<i class="fas fa-edit me-2"></i>CẬP NHẬT: ${rule.name}`;
    bootstrap.Modal.getOrCreateInstance(document.getElementById('ruleModal')).show();
}

function saveRule() {
    const days = [];
    document.querySelectorAll('input[name="daycheck"]:checked').forEach(cb => days.push(cb.value));

    const payload = {
        id: document.getElementById('r-id').value,
        name: document.getElementById('r-name').value,
        room_type: document.getElementById('r-room-type').value,
        priority: document.getElementById('r-priority').value,
        start_date: document.getElementById('r-start').value,
        end_date: document.getElementById('r-end').value,
        days_of_week: days,
        
        // CHỈ GỬI GIÁ NGÀY
        price_daily: document.getElementById('r-price-daily').value
        
        // Đã xóa price_initial, price_next để code gọn gàng
    };

    if(!payload.name || !payload.price_daily) { 
        alert("Vui lòng nhập tên sự kiện và giá ngày!"); 
        return; 
    }

    fetch('/api/prices/save-rule', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    }).then(res => res.json()).then(data => {
        if(data.success) {
            bootstrap.Modal.getInstance(document.getElementById('ruleModal')).hide();
            loadData();
        } else {
            alert(data.msg);
        }
    });
}

function deleteRule(id) {
    if(confirm("Xóa luật giá này?")) {
        fetch(`/api/prices/delete-rule/${id}`, {method: 'DELETE'})
        .then(res => res.json()).then(() => loadData());
    }
}

// Helper: Format tiền
function formatCurrency(amount) {
    if(!amount) return '0';
    return new Intl.NumberFormat('vi-VN').format(amount);
}
