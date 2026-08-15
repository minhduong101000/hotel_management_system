// ========================================================
// MODAL ĐẶT PHÒNG — chip thời lượng + tạm tính (spec 15-08)
// Dùng chung cho Sơ đồ phòng và Timeline (partial _booking_modal.html).
// Tạm tính lấy từ quote server (/api/bookings/calculate-price) —
// client không tự nhân giá để khỏi lệch với bảng giá hiệu lực.
// ========================================================

let bookingQuoteTimer = null;

function setHourlyDuration(hours) {
    const inEl = document.getElementById('bk-hourly-in');
    const outEl = document.getElementById('bk-hourly-out');
    if (!inEl || !outEl) return;
    let start;
    if (inEl.value) {
        start = new Date(inEl.value);
    } else {
        start = new Date();
        const localStart = new Date(start.getTime() - start.getTimezoneOffset() * 60000);
        inEl.value = localStart.toISOString().slice(0, 16);
    }
    const end = new Date(start.getTime() + hours * 3600000);
    const localEnd = new Date(end.getTime() - end.getTimezoneOffset() * 60000);
    outEl.value = localEnd.toISOString().slice(0, 16);
    document.querySelectorAll('[data-hour-chip]').forEach(chip => {
        chip.classList.toggle('active', Number(chip.dataset.hourChip) === hours);
    });
    scheduleBookingQuote();
}

function scheduleBookingQuote() {
    clearTimeout(bookingQuoteTimer);
    bookingQuoteTimer = setTimeout(refreshBookingQuote, 350);
}

function bkQuoteMoney(value) {
    return Number(value || 0).toLocaleString('vi-VN') + ' đ';
}

async function refreshBookingQuote() {
    const body = document.getElementById('bk-quote-body');
    const empty = document.getElementById('bk-quote-empty');
    if (!body || !empty) return;

    const type = document.getElementById('bk-type')?.value || 'daily';
    const checkIn = document.getElementById(type === 'daily' ? 'bk-daily-in' : 'bk-hourly-in')?.value;
    const checkOut = document.getElementById(type === 'daily' ? 'bk-daily-out' : 'bk-hourly-out')?.value;
    const roomId = document.getElementById('bk-room-id')?.value;
    if (!roomId || !checkIn || !checkOut || new Date(checkOut) <= new Date(checkIn)) {
        body.classList.add('d-none');
        empty.classList.remove('d-none');
        return;
    }

    try {
        const res = await fetch(api('/api/bookings/calculate-price'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                room_id: roomId,
                check_in: checkIn,
                check_out: checkOut,
                rental_type: type,
            }),
        });
        const data = await res.json();
        if (!data.success) {
            body.classList.add('d-none');
            empty.classList.remove('d-none');
            return;
        }
        const total = Number(data.quote?.total ?? data.total_amount ?? 0);
        const deposit = Number(document.getElementById('bk-deposit')?.value || 0);
        document.getElementById('bk-quote-total').textContent = bkQuoteMoney(total);
        document.getElementById('bk-quote-deposit').textContent = '− ' + bkQuoteMoney(deposit);
        document.getElementById('bk-quote-due').textContent = bkQuoteMoney(Math.max(0, total - deposit));
        const desc = document.getElementById('bk-quote-desc');
        if (desc) desc.textContent = type === 'hourly' ? 'Tiền giờ (dự kiến)' : 'Tiền phòng (tạm tính)';
        empty.classList.add('d-none');
        body.classList.remove('d-none');
    } catch (err) {
        console.error('Lỗi tạm tính đặt phòng:', err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    ['bk-daily-in', 'bk-daily-out', 'bk-hourly-in', 'bk-hourly-out', 'bk-deposit'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('change', scheduleBookingQuote);
        el.addEventListener('input', scheduleBookingQuote);
    });
    document.getElementById('tab-daily')?.addEventListener('click', scheduleBookingQuote);
    document.getElementById('tab-hourly')?.addEventListener('click', scheduleBookingQuote);
    // Mở modal với ngày giờ đã prefill (click ô trống trên lưới) -> tính luôn
    document.getElementById('bookingModal')?.addEventListener('shown.bs.modal', scheduleBookingQuote);
});
