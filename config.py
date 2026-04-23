import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'milkmanagementsecretkey')
    
    #Mysql
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'Theja@123') 
    MYSQL_DB = os.environ.get('MYSQL_DB', 'milk_management')
    MYSQL_CURSORCLASS = 'DictCursor'
    
    #session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    #email (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'thejareddy5569@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'crqozrgytxawykon')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'MilkMgmt <thejareddy5569@gmail.com>')
    
    #Otp
    OTP_EXPIRY_MINUTES = 5
    OTP_RESEND_COOLDOWN_SECONDS = 30
    
    # App
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'reddytheja65@gmail.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Theja@123')
