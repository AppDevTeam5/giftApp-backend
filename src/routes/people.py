"""
Contacts (Person): people the user saved, either by hand (friends who are
not on the app) or automatically (linked to a friend's account).  Owner: Ziyu

Routes (all need a logged-in user, and only touch that user's own contacts):
  GET    /api/people/        my contacts
  POST   /api/people/        add a contact by hand
  GET    /api/people/<id>/   one contact, with their gifts
  PATCH  /api/people/<id>/   edit a contact
  DELETE /api/people/<id>/   delete a contact (their gifts are deleted too)
"""

from flask import Blueprint

from db import Person, db
from routes.auth import is_valid_birthday
from utils import failure_response, get_body, get_current_user, success_response

people_bp = Blueprint("people", __name__)

# Fields a user may set on a contact they created by hand
PROFILE_FIELDS = [
    "name",
    "birth_month",
    "birth_day",
    "birth_year",
    "mbti",
    "hobbies",
    "additional_info",
]
# Fields a user may set on any contact, including linked ones
PERSONAL_FIELDS = ["budget", "relationship"]


# ----- helpers ------

def get_my_contact(user, person_id):
    """
    The contact with this id if it belongs to `user`, otherwise None.
    Someone else's contact counts as not found, so ids can't be probed.
    """
    return Person.query.filter_by(id=person_id, user_id=user.id).first()


def check_budget(value):
    """
    Returns an error message if `value` is not a valid budget, otherwise None.
    A budget may be empty (None) or a number that is 0 or more.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return "budget must be a number of 0 or more"
    return None


def list_item(person):
    """
    A contact as shown in the contacts list (without its gifts)
    """
    data = person.serialize()
    data.pop("gifts")
    return data


# ----- routes -----

@people_bp.route("/api/people/")
def get_people():
    """
    All of the logged-in user's contacts, sorted by name
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    people = [list_item(person) for person in user.people]
    people.sort(key=lambda p: p["name"].lower())
    return success_response({"people": people})


@people_bp.route("/api/people/", methods=["POST"])
def create_person():
    """
    Adds a contact by hand. name, birth_month and birth_day are required.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    body = get_body()
    name = body.get("name")
    birth_month = body.get("birth_month")
    birth_day = body.get("birth_day")
    birth_year = body.get("birth_year")

    if not name or birth_month is None or birth_day is None:
        return failure_response("Missing name, birth_month or birth_day", 400)
    if not is_valid_birthday(birth_month, birth_day, birth_year):
        return failure_response("Invalid birthday", 400)
    budget_error = check_budget(body.get("budget"))
    if budget_error:
        return failure_response(budget_error, 400)

    person = Person(
        user_id=user.id,
        name=name,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_year=birth_year,
        mbti=body.get("mbti"),
        hobbies=body.get("hobbies"),
        additional_info=body.get("additional_info"),
        budget=body.get("budget"),
        relationship=body.get("relationship"),
    )
    db.session.add(person)
    db.session.commit()
    return success_response(person.serialize(), 201)


@people_bp.route("/api/people/<int:person_id>/")
def get_person(person_id):
    """
    One contact, with their gifts
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    person = get_my_contact(user, person_id)
    if person is None:
        return failure_response("Contact not found")
    return success_response(person.serialize())


@people_bp.route("/api/people/<int:person_id>/", methods=["PATCH"])
def update_person(person_id):
    """
    Edits a contact; only the fields sent are changed.
    For a contact linked to a friend's account, the profile comes from the
    friend, so only budget and relationship can be changed.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    person = get_my_contact(user, person_id)
    if person is None:
        return failure_response("Contact not found")

    body = get_body()
    if person.linked_user_id is not None:
        locked = [field for field in PROFILE_FIELDS if field in body]
        if locked:
            return failure_response(
                "This contact's profile comes from your friend's account; "
                "only budget and relationship can be changed",
                400,
            )

    # Work out the birthday after the change, and check it is still valid
    birth_month = body.get("birth_month", person.birth_month)
    birth_day = body.get("birth_day", person.birth_day)
    birth_year = body.get("birth_year", person.birth_year)
    if not is_valid_birthday(birth_month, birth_day, birth_year):
        return failure_response("Invalid birthday", 400)
    if "name" in body and not body["name"]:
        return failure_response("name cannot be empty", 400)
    budget_error = check_budget(body.get("budget"))
    if budget_error:
        return failure_response(budget_error, 400)

    for field in PROFILE_FIELDS + PERSONAL_FIELDS:
        if field in body:
            setattr(person, field, body[field])
    db.session.commit()
    return success_response(person.serialize())


@people_bp.route("/api/people/<int:person_id>/", methods=["DELETE"])
def delete_person(person_id):
    """
    Deletes a contact and its gifts.
    A contact linked to a friend can't be deleted while you are friends.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    person = get_my_contact(user, person_id)
    if person is None:
        return failure_response("Contact not found")
    if person.linked_user_id is not None:
        return failure_response(
            "This contact is linked to a friend; remove the friend first", 400
        )

    data = person.serialize()
    db.session.delete(person)
    db.session.commit()
    return success_response(data)
