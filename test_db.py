from app import app, db
from sqlalchemy import inspect


def main():
    with app.app_context():
        for column in inspect(db.engine).get_columns("bookings"):
            print(column)


if __name__ == "__main__":
    main()
