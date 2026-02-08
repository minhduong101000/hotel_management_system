from models.room import Room
from models.room_price import RoomPrice
from sqlalchemy import and_

class RoomRepository:
    @staticmethod
    def get_all_rooms():
        return Room.query.order_by(Room.room_number).all()

    @staticmethod
    def get_price_for_date(room_type, target_date):
        """Logic tính giá động: Ngày lễ > Cuối tuần > Giá gốc"""
        # 1. Check ngày lễ
        special = RoomPrice.query.filter(and_(
            RoomPrice.room_type == room_type,
            RoomPrice.specific_date == target_date
        )).first()
        if special: return special.price

        # 2. Check thứ trong tuần
        day_name = target_date.strftime('%A')
        weekly = RoomPrice.query.filter(and_(
            RoomPrice.room_type == room_type,
            RoomPrice.day_of_week == day_name
        )).first()
        if weekly: return weekly.price
        
        return None # Không có giá đặc biệt