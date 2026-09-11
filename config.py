from flask_mysqldb import MySQL

mysql = MySQL()


class Config:

    # ==========================================
    # MYSQL DATABASE
    # ==========================================

    MYSQL_HOST = "localhost"

    MYSQL_USER = "root"

    MYSQL_PASSWORD = "your sql password"

    MYSQL_DB = "smart_classroom_attendance"


    # ==========================================
    # GMAIL / FLASK-MAIL
    # ==========================================

    MAIL_SERVER = "smtp.gmail.com"

    MAIL_PORT = 587

    MAIL_USE_TLS = True

    MAIL_USERNAME = "your email id"

    MAIL_PASSWORD = "16 digits password"

    MAIL_DEFAULT_SENDER = "your email id"
