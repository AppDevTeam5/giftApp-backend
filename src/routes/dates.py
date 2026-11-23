"""
Birthday and festival reminders.  Owner: Alya

Routes:
  GET    /api/upcoming/?days=30     birthdays (friends + saved people), special days
                                    and events I'm going to, soonest first
  GET    /api/special-days/         festivals + my personal dates
  POST   /api/special-days/         add a personal date {name, date, recurring}
  DELETE /api/special-days/<id>/    delete one of my dates

Festivals are added ahead of time by scripts/seed_festivals.py.
"""

import datetime

from flask import Blueprint, request
from sqlalchemy import or_

from db import SpecialDay, db
from utils import failure_response, get_body, get_current_user, success_response

dates_bp = Blueprint("dates", __name__)


# ---------- helper functions ----------


def safe_date(year, month, day):
    """
    Builds a date, moving Feb 29 to Feb 28 in years that are not leap years
    """
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return datetime.date(year, 2, 28)


def next_yearly(month, day, today):
    """
    The next time a yearly date (birthday, anniversary...) happens,
    today included
    """
    this_year = safe_date(today.year, month, day)
    if this_year >= today:
        return this_year
    return safe_date(today.year + 1, month, day)


def next_occurrence(special_day, today):
    """
    When a special day happens next. Recurring days repeat every year;
    the others happen only on their exact date.
    """
    if special_day.recurring:
        return next_yearly(special_day.date.month, special_day.date.day, today)
    return special_day.date


def visible_special_days(user):
    """
    The user's own special days plus the shared festivals (user_id is None)
    """
    return SpecialDay.query.filter(
        or_(SpecialDay.user_id == user.id, SpecialDay.user_id.is_(None))
    ).all()


# ---------- routes ----------


@dates_bp.route("/api/upcoming/")
def get_upcoming():
    """
    Everything coming up in the next `days` days (default 30), soonest first:
    contacts' birthdays, special days and festivals, and events I host or
    accepted an invitation to
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Read ?days=
    days = request.args.get("days", default=30, type=int)
    if days is None or days < 0 or days > 366:
        return failure_response("days must be a number from 0 to 366", 400)

    today = datetime.date.today()
    last_day = today + datetime.timedelta(days=days)
    items = []

    def add(kind, name, when, **extra):
        """Adds one item to the list if it falls inside the window"""
        if today <= when <= last_day:
            items.append(
                {
                    "kind": kind,
                    "name": name,
                    "date": when.isoformat(),
                    "days_left": (when - today).days,
                    **extra,
                }
            )

    # Birthdays of my contacts (friends on the app are contacts too)
    for person in user.people:
        info = person.profile()
        when = next_yearly(info["birth_month"], info["birth_day"], today)
        add("birthday", "%s's birthday" % info["name"], when, person_id=person.id)

    # My special days and the shared festivals
    for special_day in visible_special_days(user):
        kind = "festival" if special_day.user_id is None else "special_day"
        add(kind, special_day.name, next_occurrence(special_day, today),
            special_day_id=special_day.id)

    # Events I host or said yes to
    accepted = [
        invitation.event
        for invitation in user.invitations
        if invitation.status == "accepted"
    ]
    for event in user.hosted_events + accepted:
        add("event", event.title, event.starts_at.date(), event_id=event.id)

    items.sort(key=lambda item: item["date"])
    return success_response({"upcoming": items})


@dates_bp.route("/api/special-days/")
def get_special_days():
    """
    Returns the shared festivals and the logged-in user's own special days
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    days = visible_special_days(user)
    days.sort(key=lambda day: (day.date.month, day.date.day))
    return success_response({"special_days": [day.serialize() for day in days]})


@dates_bp.route("/api/special-days/", methods=["POST"])
def create_special_day():
    """
    Adds a personal date for the logged-in user.
    name and date ("YYYY-MM-DD") are required; recurring defaults to true.
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Read the body
    body = get_body()
    name = body.get("name")
    date_text = body.get("date")
    recurring = body.get("recurring", True)
    if not name or date_text is None:
        return failure_response("Missing name or date", 400)

    # Check the date and recurring values
    try:
        date = datetime.date.fromisoformat(date_text)
    except (TypeError, ValueError):
        return failure_response("date must be YYYY-MM-DD", 400)
    if not isinstance(recurring, bool):
        return failure_response("recurring must be true or false", 400)

    # All checks passed --> create the row
    special_day = SpecialDay(user_id=user.id, name=name, date=date, recurring=recurring)
    db.session.add(special_day)
    db.session.commit()
    return success_response(special_day.serialize(), 201)


@dates_bp.route("/api/special-days/<int:day_id>/", methods=["DELETE"])
def delete_special_day(day_id):
    """
    Deletes one of the logged-in user's own special days.
    Shared festivals cannot be deleted here.
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Does it exist?
    special_day = SpecialDay.query.filter_by(id=day_id).first()
    if special_day is None:
        return failure_response("Special day not found")

    # Only the owner can delete it (festivals have no owner)
    if special_day.user_id != user.id:
        return failure_response("You can only delete your own special days", 403)

    data = special_day.serialize()
    db.session.delete(special_day)
    db.session.commit()
    return success_response(data)
