"""Nguồn chân lý duy nhất cho câu hỏi 'phòng này có bận không'.

Trước 19-08 mỗi đường đặt phòng tự kiểm tra một kiểu: đường đặt lẻ xét cả giờ
thực tế lẫn khách ở quá hẹn, còn đường đặt đoàn và tìm phòng trống chỉ so giờ
dự kiến nên vẫn mời phòng đang có người.

HỢP ĐỒNG: mọi tham số datetime là GIỜ NGHIỆP VỤ naive (cùng hệ với *_expected).
"""

from models import BookingRoom
from services import time_service
from services.tenant_service import tenant_query

ACTIVE_STATUSES = ('booked', 'checked_in')


def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _row_window(row):
    """Khoảng thời gian phòng bị chiếm bởi một dòng BookingRoom.

    Trả về (start, end, busy_without_end): busy_without_end nghĩa là khách đã
    check-in nhưng CHƯA có mốc check-out thật -> coi như chiếm phòng vô thời
    hạn, kể cả khi đã quá giờ dự kiến (khách ở quá hẹn). Phòng chỉ thật sự
    trống trở lại khi có check_out_actual (hoặc trạng thái không còn active).
    """
    # *_actual lưu UTC còn *_expected đã là giờ nghiệp vụ. Phải quy đổi TRƯỚC
    # khi trộn, nếu không cửa sổ bận của khách đang ở sẽ bắt đầu sớm 7 tiếng và
    # chặn oan những booking hợp lệ.
    start = (
        time_service.to_business_naive(row.check_in_actual)
        if row.check_in_actual
        else _naive(row.check_in_expected)
    )

    if row.status == 'checked_in' and not row.check_out_actual:
        # Đã check-in thật nhưng chưa check-out thật: đang chiếm phòng ngay
        # bây giờ, không thể biết chắc khi nào sẽ trả. Không được chốt cửa sổ
        # bận tại "now" rồi so [start,now) với cửa sổ ứng viên bắt đầu đúng
        # lúc "now" — biên sẽ lệch và bỏ sót đúng ca khách đang ở quá hẹn.
        return start, None, True

    end = (
        time_service.to_business_naive(row.check_out_actual)
        if row.check_out_actual
        else _naive(row.check_out_expected)
    )
    return start, end, False


def _conflicting_rows(rows, start_dt, end_dt):
    for row in rows:
        row_start, row_end, busy_without_end = _row_window(row)
        if busy_without_end:
            yield row
            continue
        if not row_start or not row_end:
            continue
        # [a,b) giao [c,d) khi a < d và b > c
        if row_start < end_dt and row_end > start_dt:
            yield row


def has_room_conflict(
    *,
    room_id,
    start_dt,
    end_dt,
    exclude_booking_room_id=None,
    now=None,
) -> bool:
    start_dt = _naive(start_dt)
    end_dt = _naive(end_dt)
    if not start_dt or not end_dt:
        return False

    # "now" không còn cần cho phép tính (khách chưa check-out thật -> luôn coi
    # là bận vô thời hạn, xem _row_window) — vẫn giữ trong chữ ký để khớp hợp
    # đồng interface và cho lời gọi tương lai truyền một mốc "bây giờ" đồng
    # nhất giữa nhiều lời gọi trong cùng một request.
    now = now or time_service.business_now_naive()
    query = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status.in_(ACTIVE_STATUSES),
    )
    if exclude_booking_room_id is not None:
        query = query.filter(BookingRoom.id != int(exclude_booking_room_id))

    return any(_conflicting_rows(query.all(), start_dt, end_dt))


def occupied_room_ids(*, start_dt, end_dt, now=None) -> set:
    start_dt = _naive(start_dt)
    end_dt = _naive(end_dt)
    if not start_dt or not end_dt:
        return set()

    now = now or time_service.business_now_naive()
    rows = tenant_query(BookingRoom).filter(
        BookingRoom.status.in_(ACTIVE_STATUSES),
    ).all()

    return {row.room_id for row in _conflicting_rows(rows, start_dt, end_dt)}
