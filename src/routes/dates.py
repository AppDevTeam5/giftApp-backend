"""
Birthday and festival reminders.  Owner: TBD

Planned routes:
  GET    /api/upcoming/?days=30     birthdays (friends + saved people) and special days, soonest first
  GET    /api/special-days/         festivals + my personal dates
  POST   /api/special-days/         add a personal date {name, date}
  DELETE /api/special-days/<id>/    delete one of my dates

Festivals are added ahead of time by scripts/seed_festivals.py.
"""

from flask import Blueprint

dates_bp = Blueprint("dates", __name__)
