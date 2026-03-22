import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'luxury-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'mysql+pymysql://root:123456@localhost/Hotel_Management_System'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Branding info for printable invoices/receipts
    HOTEL_NAME = os.environ.get('HOTEL_NAME', 'HOTEL POS PRO')
    HOTEL_BRANCH = os.environ.get('HOTEL_BRANCH', 'Chi nhanh trung tam')
    HOTEL_ADDRESS = os.environ.get('HOTEL_ADDRESS', '123 Duong ABC, Ha Noi')
    HOTEL_PHONE = os.environ.get('HOTEL_PHONE', '0987 654 321')
    HOTEL_EMAIL = os.environ.get('HOTEL_EMAIL', 'contact@hotelpos.vn')
    HOTEL_LOGO_URL = os.environ.get('HOTEL_LOGO_URL', '/static/img/hotel-logo.png')
