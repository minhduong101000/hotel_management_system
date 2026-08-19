"""Nguồn chân lý duy nhất cho câu hỏi 'phòng này có bận không'.

Trước 19-08 mỗi đường đặt phòng tự kiểm tra một kiểu: đường đặt lẻ xét cả giờ
thực tế lẫn khách ở quá hẹn, còn đường đặt đoàn và tìm phòng trống chỉ so giờ
dự kiến nên vẫn mời phòng đang có người.

HỢP ĐỒNG: mọi tham số datetime là GIỜ NGHIỆP VỤ naive (cùng hệ với *_expected).

Hai bất biến mà cửa sổ bận của một khách ĐANG Ở (checked_in, chưa có
check_out_actual) phải thoả ĐỒNG THỜI — xem `_row_window`:

- Bất biến A: khách còn trong hạn (chưa quá giờ trả dự kiến) không được khoá
  cứng những ngày tương lai xa (vd tuần sau) — lễ tân vẫn phải nhận đặt trước
  được cho phòng đó.
- Bất biến B: khách đã quá giờ trả dự kiến vẫn đang chiếm phòng THẬT tại thời
  điểm hiện tại — một đặt phòng có cửa sổ trùm qua "bây giờ" vẫn phải bị chặn.
"""

from models import BookingRoom
from services import time_service
from services.tenant_service import tenant_query

ACTIVE_STATUSES = ('booked', 'checked_in')

# Chế độ cửa sổ bận trả về bởi _row_window:
#   'unbounded'   -> bận vô thời hạn, chặn mọi cửa sổ ứng viên bất kể xa gần.
#   'capped_now'  -> bận từ start tới ĐÚNG "now" (bao gồm "now"), không chặn
#                    xa hơn "now" — dùng cho khách quá hẹn nhưng còn mốc dự
#                    kiến để biết họ lẽ ra đã phải trả.
#   'bounded'     -> cửa sổ nửa-mở [start, end) bình thường.


def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _row_window(row, now):
    """Khoảng thời gian phòng bị chiếm bởi một dòng BookingRoom.

    Trả về (start, end, mode) — xem hằng số mode ở trên.
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
        expected_end = _naive(row.check_out_expected)

        if expected_end is None:
            # Không có cả giờ trả dự kiến lẫn giờ trả thật: không có mốc nào
            # để đoán khi nào khách rời phòng -> bận vô thời hạn.
            return start, None, 'unbounded'

        if expected_end <= now:
            # Đã tới/quá giờ trả dự kiến nhưng chưa check-out thật (Bất biến
            # B): khách đang chiếm phòng NGAY BÂY GIỜ. Chốt cửa sổ tại "now"
            # (bao gồm "now") để không giả định họ còn ở đó xa hơn hiện tại —
            # nếu không, mọi phòng có khách sẽ không nhận được đặt trước
            # tương lai cho tới khi khách thật sự check-out (Bất biến A).
            return start, now, 'capped_now'

        # Chưa tới giờ trả dự kiến: cửa sổ bận bình thường theo giờ dự kiến,
        # không chặn những ngày sau đó (Bất biến A).
        return start, expected_end, 'bounded'

    end = (
        time_service.to_business_naive(row.check_out_actual)
        if row.check_out_actual
        else _naive(row.check_out_expected)
    )
    return start, end, 'bounded'


def _conflicting_rows(rows, start_dt, end_dt, now):
    for row in rows:
        row_start, row_end, mode = _row_window(row, now)

        if mode == 'unbounded':
            yield row
            continue

        if not row_start or not row_end:
            continue

        if mode == 'capped_now':
            # [a, b] đóng ở đầu cuối: "now" tính là bận, để bắt đúng ca một
            # đặt phòng bắt đầu chính xác lúc "now" (khách vẫn đang ở đó).
            if row_start < end_dt and row_end >= start_dt:
                yield row
            continue

        # 'bounded': [a,b) nửa-mở giao [c,d) khi a < d và b > c. Nửa-mở để
        # hai booking nối ca đúng giờ (trả 12:00, nhận 12:00) không bị coi
        # là trùng.
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

    now = now or time_service.business_now_naive()
    query = tenant_query(BookingRoom).filter(
        BookingRoom.room_id == room_id,
        BookingRoom.status.in_(ACTIVE_STATUSES),
    )
    if exclude_booking_room_id is not None:
        query = query.filter(BookingRoom.id != int(exclude_booking_room_id))

    return any(_conflicting_rows(query.all(), start_dt, end_dt, now))


def occupied_room_ids(*, start_dt, end_dt, now=None) -> set:
    start_dt = _naive(start_dt)
    end_dt = _naive(end_dt)
    if not start_dt or not end_dt:
        return set()

    now = now or time_service.business_now_naive()
    rows = tenant_query(BookingRoom).filter(
        BookingRoom.status.in_(ACTIVE_STATUSES),
    ).all()

    return {row.room_id for row in _conflicting_rows(rows, start_dt, end_dt, now)}
