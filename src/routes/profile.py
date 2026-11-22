"""
Profiles ("friend cards").  Owner: Ziyu

A user's friend card is filled in from the sign-up questionnaire.

Routes (all need a logged-in user):
  GET   /api/me/          my full profile
  PATCH /api/me/          update my profile (questionnaire answers, yearly budget)
  GET   /api/users/<id>/  another user's friend card (full card for friends only)
"""

from flask import Blueprint

from db import User, db
from routes.auth import is_valid_birthday
from routes.friends import are_friends, friend_status
from utils import failure_response, get_body, get_current_user, success_response

profile_bp = Blueprint("profile", __name__)

EDITABLE_FIELDS = [
    "name",
    "birth_month",
    "birth_day",
    "birth_year",
    "mbti",
    "hobbies",
    "additional_info",
    "yearly_budget",
]


# ---------- helper functions ----------


def friend_card(user):
    """
    What a friend may see: the profile, but not the email or the budget
    """
    return {
        "id": user.id,
        "name": user.name,
        "birth_month": user.birth_month,
        "birth_day": user.birth_day,
        "birth_year": user.birth_year,
        "mbti": user.mbti,
        "hobbies": user.hobbies,
        "additional_info": user.additional_info,
    }


# ---------- routes ----------


@profile_bp.route("/api/me/")
def get_me():
    """
    The logged-in user's full profile, including email and yearly budget
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)
    return success_response(user.serialize())


@profile_bp.route("/api/me/", methods=["PATCH"])
def update_me():
    """
    Updates the logged-in user's profile; only the fields sent are changed
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    body = get_body()
    if "name" in body and not body["name"]:
        return failure_response("name cannot be empty", 400)

    # Check the birthday as it will be after the change
    birth_month = body.get("birth_month", user.birth_month)
    birth_day = body.get("birth_day", user.birth_day)
    birth_year = body.get("birth_year", user.birth_year)
    if not is_valid_birthday(birth_month, birth_day, birth_year):
        return failure_response("Invalid birthday", 400)

    if "yearly_budget" in body:
        budget = body["yearly_budget"]
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget < 0:
            return failure_response("yearly_budget must be a number of 0 or more", 400)

    for field in EDITABLE_FIELDS:
        if field in body:
            setattr(user, field, body[field])
    db.session.commit()
    return success_response(user.serialize())


@profile_bp.route("/api/users/<int:user_id>/")
def get_user_card(user_id):
    """
    Another user's friend card. Friends see the full card;
    anyone else sees only the name. Includes how they relate to me.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    other = User.query.filter_by(id=user_id).first()
    if other is None:
        return failure_response("User not found")
    if other.id == user.id:
        return success_response(user.serialize())

    if are_friends(user, other):
        card = friend_card(other)
    else:
        card = other.simple_serialize()
    card["friend_status"] = friend_status(user, other)
    return success_response(card)
