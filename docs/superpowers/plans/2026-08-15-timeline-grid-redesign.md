# Plan: Redesign màn Timeline (lưới phòng × ngày + restyle modal)

> **Spec:** docs/superpowers/specs/2026-08-15-timeline-grid-redesign-design.md
> Thực thi inline theo nếp SDD → TDD → thực thi → nghiệm thu, commit theo task.

**Bất biến phải giữ (test đang khóa):**
- `id="visualization" class="d-none"`, `id="timeline-loading-state"`,
  `data-state data-state--loading`, "Đang tải Timeline" (frontdesk_ui_polish)
- Label-for đủ cho `edit-*`, `refund-reason`, `bd-service-search`, `bd-note`,
  `bd-rental-type`, `bd-room-select`, `bk-*`, `group_*` (accessibility_markup)
- `reschedule-status` role=alert + aria-live assertive; `aria-busy="false"`;
  `data-modal-initial-focus` trên `reschedule-room-select`; btn-close có aria-label
- JS giữ: `beginBookingSubmission`/`endBookingSubmission`, `showRescheduleStatus`,
  `setRescheduleButtonBusy`, không `fetch(`/api/customers` trần (ui_regression)
- Browser B2/B4 mở modal qua JS: giữ `bookingModal`, `editBookingModal`,
  `bk-phone`, `bk-name`, `edit-booking-id`, `edit-checkin/out`, `btn-add-room`

## Task 1 — API field cấu trúc (TDD)
- [x] RED: `tests/test_timeline_api_fields.py` — groups có `room_type`; items có
      `customer_name`, `rental_type`, `room_count`, `is_overstay` (bool)
- [x] GREEN: bổ sung field trong `get_timeline` (timeline_controller)
- [x] Commit `feat: timeline API returns structured fields for grid renderer`

## Task 2 — Lưới phòng × ngày (JS + CSS + template)
- [x] timeline.html: header + 4 stat card (`tlg-stats`), toolbar trắng 1 hàng
      (giữ mọi id, thêm `timeline-view-2weeks/month`, thêm option filter
      `hourly`/`group`), legend chấm màu, giữ nguyên khối data-state
- [x] timeline_manager.js: `renderTimeline()` vẽ lưới (thay vis), giữ nguyên
      tên hàm public; `getTimelineRange` thêm 2 mode; click ô/thanh giữ handler;
      stats client-side; bỏ tham chiếu `vis.*`
- [x] style.css: block `tlg-*` mới; xóa block vá `.vis-*` cũ
- [x] Xóa 2 thẻ unpkg khỏi timeline.html
- [x] Chạy: pytest markup/regression + mở trang xác nhận không lỗi console
- [x] Commit `feat: replace vis-timeline with custom room-day grid per design`

## Task 3 — Modal Đặt phòng
- [x] Restyle 2 cột + sidebar "Tạm tính" (render từ quote của
      `calculateQuickDeposit`), chip 2h/4h/6h điền `bk-hourly-out`, giữ mọi id/label
- [x] pytest accessibility + workflow_modal_markup xanh
- [x] Commit `feat: redesign booking modal with quote sidebar and hour chips`

## Task 4 — editBookingModal + bookingDetailModal
- [x] Restyle theo pos-modal (header trắng, badge trạng thái, nút teal);
      không đổi field/luồng
- [x] Commit `feat: restyle edit and POS detail modals to design language`

## Task 5 — Thanh toán
- [x] Segmented Tiền mặt/Chuyển khoản/Thẻ → `payment_method` trong payload
      (cash|banking|credit_card); RED/GREEN test method được ghi vào Payment
      nếu chưa có test; restyle modal
- [x] Commit `feat: checkout modal redesign with payment method selector`

## Task 6 — Đoàn + QR + font
- [x] Restyle group booking (card phòng trống thay checkbox-look, giữ input),
      group checkout (bảng per-room + box tổng), QR (dropzone)
- [x] base.html: link Google Fonts Be Vietnam Pro
- [x] Commit `feat: restyle group and QR modals, load Be Vietnam Pro`

## Nghiệm thu
- [x] `pytest -m "not mysql and not browser"` xanh toàn bộ
- [x] Docker rebuild web + browser suite (B1–B4) xanh
- [x] Screenshot timeline + modal đối chiếu mockup, đính vào báo cáo
- [x] Push dev
