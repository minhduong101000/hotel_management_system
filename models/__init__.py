from .user import User
from .room import Room
from .customer import Customer
from .booking import Booking
from .service import Service
from .payment import Payment

# Giúp IDE nhận diện được export
__all__ = ['User', 'Room', 'Customer', 'Booking', 'Service', 'Payment']