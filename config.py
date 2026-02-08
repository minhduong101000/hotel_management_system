import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/Hotel_Management_System'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Secret Key dùng cho Session và Flash message (chống hack)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chuoi-ky-tu-ngau-nhien-bao-mat-123'