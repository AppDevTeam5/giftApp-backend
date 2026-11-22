"""
Accounts and login.  Owner: Ziyu

Routes:
  POST /api/register/   create an account; returns user + tokens
  POST /api/login/      log in; returns user + tokens
  POST /api/session/    send the update token as Bearer; returns fresh tokens
  POST /api/logout/     end the current session

Every protected route elsewhere uses utils.get_current_user().
The app sends the session token as:  Authorization: Bearer <session_token>
"""

import datetime

from flask import Blueprint, request

from db import User, db
from utils import failure_response, get_body, get_current_user, success_response

auth_bp = Blueprint("auth", __name__)


def tokens(user):
    """
    The token fields the app saves after register, login or refresh
    """
    return {
        "session_token": user.session_token,
        "session_expiration": user.session_expiration.isoformat(),
        "update_token": user.update_token,
    }


def is_valid_birthday(month, day, year=None):
    """
    True if month/day (and year, if given) form a real date.
    Uses 2000 (a leap year) when there is no year, so Feb 29 is allowed.
    """
    try:
        datetime.date(year if year is not None else 2000, month, day)
        return True
    except (TypeError, ValueError):
        return False


@auth_bp.route("/api/register/", methods=["POST"])
def register():
    """
    Creates an account and logs the user in
    """
    body = get_body()
    email = body.get("email")
    password = body.get("password")
    name = body.get("name")
    birth_month = body.get("birth_month")
    birth_day = body.get("birth_day")
    birth_year = body.get("birth_year")

    if not email or not password or not name or birth_month is None or birth_day is None:
        return failure_response(
            "Missing email, password, name, birth_month or birth_day", 400
        )
    if not is_valid_birthday(birth_month, birth_day, birth_year):
        return failure_response("Invalid birthday", 400)
    if User.query.filter_by(email=email).first() is not None:
        return failure_response("An account with this email already exists", 409)

    user = User(
        email=email,
        password=password,
        name=name,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_year=birth_year,
    )
    db.session.add(user)
    db.session.commit()
    return success_response({"user": user.serialize(), **tokens(user)}, 201)


@auth_bp.route("/api/login/", methods=["POST"])
def login():
    """
    Logs in with email and password; returns fresh tokens
    """
    body = get_body()
    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        return failure_response("Missing email or password", 400)

    user = User.query.filter_by(email=email).first()
    if user is None or not user.verify_password(password):
        return failure_response("Incorrect email or password", 401)

    user.renew_session()
    db.session.commit()
    return success_response({"user": user.serialize(), **tokens(user)})


@auth_bp.route("/api/session/", methods=["POST"])
def refresh_session():
    """
    Exchanges the update token (sent as Bearer) for fresh tokens
    """
    header = request.headers.get("Authorization", "")
    update_token = header.replace("Bearer ", "", 1).strip()
    if not update_token:
        return failure_response("Missing update token", 401)

    user = User.query.filter_by(update_token=update_token).first()
    if user is None:
        return failure_response("Invalid update token", 401)

    user.renew_session()
    db.session.commit()
    return success_response(tokens(user))


@auth_bp.route("/api/logout/", methods=["POST"])
def logout():
    """
    Ends the current session by expiring the session token now
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    user.session_expiration = datetime.datetime.now()
    db.session.commit()
    return success_response({"message": "Logged out"})
