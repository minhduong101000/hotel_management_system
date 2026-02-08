from models.booking import BookingRoom
from sqlalchemy import and_

class BookingRepository:
    @staticmethod
    def get_bookings_in_range(start_date, end_date):
        # Lấy booking dính tới khoảng ngày hiển thị
        return BookingRoom.query.filter(
            and_(
                BookingRoom.check_in < end_date,
                BookingRoom.check_out > start_date
            )
        ).all()