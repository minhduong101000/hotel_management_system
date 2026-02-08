# models/__init__.py

from .base import db
from .user import User
from .customer import Customer
from .room import Room
from .room_price import RoomPrice
from .booking import Booking, BookingRoom
from .service import Service, BookingService
from .invoice import Invoice