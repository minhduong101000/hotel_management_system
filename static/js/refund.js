// ========================================================
// FORM HOÀN TIỀN (chính sách 14-08-2026)
// Mọi con số hiển thị lấy từ server (/api/refunds/preview) —
// client không tự nhân % để tránh lệch với trần cứng phía server.
// ========================================================

let refundBookingId = null;
let refundPreviewTimer = null;

function openRefundModal(bookingId) {
    refundBookingId = bookingId ?? window.currentRefundBooking ?? null;
    if (!refundBookingId) {
        alert('Không xác định được đơn đặt phòng để hoàn tiền.');
        return;
    }
    showRefundError('');
    document.getElementById('refund-reason-input').value = '';
    document.getElementById('refund-percent-input').value = '';
    document.getElementById('refund-amount-input').value = '';
    requestRefundPreview();
    bootstrap.Modal.getOrCreateInstance(document.getElementById('refundModal')).show();
}

function refundFormPayload() {
    const base = document.querySelector('input[name="refund-base"]:checked')?.value || 'unused';
    const percentRaw = document.getElementById('refund-percent-input').value;
    const amountRaw = document.getElementById('refund-amount-input').value;
    const payload = { booking_id: refundBookingId, base: base };
    if (amountRaw) {
        payload.amount = parseFloat(amountRaw);
    } else if (percentRaw) {
        payload.percent = parseFloat(percentRaw);
    }
    return payload;
}

function fmtRefundMoney(value) {
    return (value || 0).toLocaleString('vi-VN') + ' đ';
}

function requestRefundPreview() {
    const payload = refundFormPayload();
    if (payload.percent === undefined && payload.amount === undefined) {
        payload.percent = 100; // chỉ để xem ngữ cảnh; số thật do người dùng nhập
    }
    fetch(api('/api/refunds/preview'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
        .then((res) => res.json())
        .then((d) => {
            if (!d.success) { showRefundError(d.msg); return; }
            document.getElementById('refund-cap').textContent = fmtRefundMoney(d.data.cap);
            document.getElementById('refund-base-value').textContent = fmtRefundMoney(d.data.base_value);
            document.getElementById('refund-already').textContent = fmtRefundMoney(d.data.already_refunded);
            document.getElementById('refund-preview-amount').textContent = fmtRefundMoney(d.data.refund_amount);
            document.getElementById('refund-confirm-amount').textContent = fmtRefundMoney(d.data.refund_amount);
            showRefundError('');
        })
        .catch(() => showRefundError('Không tải được báo giá hoàn tiền.'));
}

function showRefundError(message) {
    const box = document.getElementById('refund-error');
    if (box) box.textContent = message || '';
}

function submitRefund() {
    const reasonInput = document.getElementById('refund-reason-input');
    const reason = reasonInput.value.trim();
    if (!reason) {
        showRefundError('Cần nhập lý do hoàn tiền.');
        reasonInput.focus();
        return;
    }
    const payload = refundFormPayload();
    if (payload.percent === undefined && payload.amount === undefined) {
        showRefundError('Nhập phần trăm hoặc số tiền cần hoàn.');
        return;
    }
    payload.payment_method = document.getElementById('refund-method').value;
    payload.reason = reason;
    payload.client_key = crypto.randomUUID(); // idempotency: retry không tạo dòng trùng

    const btn = document.getElementById('btn-confirm-refund');
    btn.disabled = true;
    fetch(api('/api/refunds'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
        .then((res) => res.json())
        .then((d) => {
            btn.disabled = false;
            if (!d.success) { showRefundError(d.msg); return; }
            alert('Đã hoàn ' + fmtRefundMoney(d.data.refund_amount) + ' cho khách.');
            bootstrap.Modal.getInstance(document.getElementById('refundModal'))?.hide();
            if (typeof loadBillingList === 'function') loadBillingList();
        })
        .catch(() => {
            btn.disabled = false;
            showRefundError('Lỗi hệ thống khi ghi nhận hoàn tiền.');
        });
}

// Hóa đơn khách: chỉ render các dòng hoàn CÒN HIỆU LỰC (server đã lọc cặp sai/đảo)
function renderRefunds(refunds) {
    const section = document.getElementById('md-refunds-section');
    const body = document.getElementById('md-refunds-body');
    if (!section || !body) return;
    body.replaceChildren();
    if (!refunds || !refunds.length) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';
    refunds.forEach((r) => {
        const tr = document.createElement('tr');
        const time = document.createElement('td');
        time.textContent = r.time || '';
        const note = document.createElement('td');
        note.textContent = 'Hoàn tiền (' + (r.method || 'cash') + ')';
        const amount = document.createElement('td');
        amount.className = 'text-end';
        amount.textContent = '-' + fmtRefundMoney(r.amount);
        tr.append(time, note, amount);
        body.appendChild(tr);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    ['refund-percent-input', 'refund-amount-input'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', () => {
            clearTimeout(refundPreviewTimer);
            refundPreviewTimer = setTimeout(requestRefundPreview, 300);
        });
    });
    document.querySelectorAll('input[name="refund-base"]').forEach((el) => {
        el.addEventListener('change', requestRefundPreview);
    });
});
