"""
Gifts and the yearly budget.  Owner: Ziyu

A gift belongs to one of the user's contacts (Person). Its status is
"idea", "bought" or "given"; only bought and given gifts count as money spent,
in the year of the gift's date. Budgets (the user's yearly budget and each
contact's budget) are per calendar year.

Routes (all need a logged-in user, and only touch that user's own gifts):
  POST   /api/people/<id>/gifts/   add a gift for a contact
  PATCH  /api/gifts/<id>/          edit a gift, e.g. idea -> bought
  DELETE /api/gifts/<id>/          delete a gift
  GET    /api/budget/?year=2026    budget summary (year is optional, default this year)
"""

import datetime

from flask import Blueprint, request

from db import GIFT_STATUSES, Gift, Person, db
from utils import failure_response, get_body, get_current_user, success_response

budget_bp = Blueprint("budget", __name__)

EDITABLE_FIELDS = ["name", "price", "status", "url", "date"]
SPENT_STATUSES = ["bought", "given"]


# ---------- helper functions ----------


def check_gift_fields(body):
    """
    Checks the gift fields that were sent.
    Returns (error_message, None) if something is wrong,
    otherwise (None, parsed_date) where parsed_date is a date, None, or
    "not sent" if the body has no date field.
    """
    if "name" in body and not body["name"]:
        return "name cannot be empty", None

    price = body.get("price")
    if price is not None and (
        isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0
    ):
        return "price must be a number of 0 or more", None

    if "status" in body and body["status"] not in GIFT_STATUSES:
        return "status must be one of: " + ", ".join(GIFT_STATUSES), None

    if "date" not in body:
        return None, "not sent"
    if body["date"] is None:
        return None, None
    try:
        return None, datetime.date.fromisoformat(body["date"])
    except (TypeError, ValueError):
        return "date must look like YYYY-MM-DD", None


def get_my_gift(user, gift_id):
    """
    The gift with this id if it belongs to one of `user`'s contacts, otherwise None
    """
    return (
        Gift.query.join(Person)
        .filter(Gift.id == gift_id, Person.user_id == user.id)
        .first()
    )


def spent(gifts, year):
    """
    Money spent on these gifts in `year`: bought or given, with a price,
    dated in that year
    """
    return round(
        float(sum(
            gift.price
            for gift in gifts
            if gift.status in SPENT_STATUSES
            and gift.price is not None
            and gift.date is not None
            and gift.date.year == year
        )),
        2,
    )


def budget_summary(user, year):
    """
    The user's spending in `year`: overall, and for every contact that has
    a budget or any spending that year
    """
    people = []
    total_spent = 0.0
    for person in user.people:
        person_spent = spent(person.gifts, year)
        total_spent += person_spent
        if person.budget is None and person_spent == 0:
            continue
        people.append(
            {
                "person": person.simple_serialize(),
                "budget": person.budget,
                "spent": person_spent,
                "remaining": round(person.budget - person_spent, 2)
                if person.budget is not None
                else None,
                "over_budget": person.budget is not None and person_spent > person.budget,
            }
        )
    people.sort(key=lambda p: p["spent"], reverse=True)

    total_spent = round(total_spent, 2)
    return {
        "year": year,
        "yearly_budget": user.yearly_budget,
        "spent": total_spent,
        "remaining": round(user.yearly_budget - total_spent, 2),
        "over_budget": total_spent > user.yearly_budget,
        "people": people,
    }


def with_budget_warnings(gift, user):
    """
    The gift's JSON plus warnings if, after this change, its year is over
    the yearly budget or its contact is over their budget
    """
    data = gift.serialize()
    if gift.status in SPENT_STATUSES and gift.date is not None:
        year = gift.date.year
        person = gift.person
        person_spent = spent(person.gifts, year)
        data["person_over_budget"] = person.budget is not None and person_spent > person.budget
        data["over_yearly_budget"] = budget_summary(user, year)["over_budget"]
    return data


# ---------- routes ----------


@budget_bp.route("/api/people/<int:person_id>/gifts/", methods=["POST"])
def add_gift(person_id):
    """
    Adds a gift for one of the logged-in user's contacts.
    A bought or given gift with no date gets today's date, so it counts this year.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    person = Person.query.filter_by(id=person_id, user_id=user.id).first()
    if person is None:
        return failure_response("Contact not found")

    body = get_body()
    if not body.get("name"):
        return failure_response("Missing name", 400)
    error, date = check_gift_fields(body)
    if error:
        return failure_response(error, 400)

    status = body.get("status", "idea")
    if date == "not sent":
        date = None
    if status in SPENT_STATUSES and date is None:
        date = datetime.date.today()

    gift = Gift(
        person_id=person.id,
        name=body["name"],
        price=body.get("price"),
        status=status,
        url=body.get("url"),
        date=date,
    )
    db.session.add(gift)
    db.session.commit()
    return success_response(with_budget_warnings(gift, user), 201)


@budget_bp.route("/api/gifts/<int:gift_id>/", methods=["PATCH"])
def update_gift(gift_id):
    """
    Edits a gift; only the fields sent are changed.
    Marking a gift bought or given with no date sets the date to today.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    gift = get_my_gift(user, gift_id)
    if gift is None:
        return failure_response("Gift not found")

    body = get_body()
    error, date = check_gift_fields(body)
    if error:
        return failure_response(error, 400)

    for field in EDITABLE_FIELDS:
        if field == "date":
            if date != "not sent":
                gift.date = date
        elif field in body:
            setattr(gift, field, body[field])

    if gift.status in SPENT_STATUSES and gift.date is None:
        gift.date = datetime.date.today()
    db.session.commit()
    return success_response(with_budget_warnings(gift, user))


@budget_bp.route("/api/gifts/<int:gift_id>/", methods=["DELETE"])
def delete_gift(gift_id):
    """
    Deletes a gift
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    gift = get_my_gift(user, gift_id)
    if gift is None:
        return failure_response("Gift not found")

    data = gift.serialize()
    db.session.delete(gift)
    db.session.commit()
    return success_response(data)


@budget_bp.route("/api/budget/")
def get_budget():
    """
    The logged-in user's budget summary for a year (?year=2026, default this year)
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    year_text = request.args.get("year")
    if year_text is None:
        year = datetime.date.today().year
    elif year_text.isdigit():
        year = int(year_text)
    else:
        return failure_response("year must be a number like 2026", 400)

    return success_response(budget_summary(user, year))
