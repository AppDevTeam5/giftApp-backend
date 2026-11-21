"""
Gifts and yearly budget.  Owner: TBD

Planned routes:
  POST   /api/people/<id>/gifts/   add a gift {name, price, status, url, date}
  PATCH  /api/gifts/<id>/          edit, e.g. idea -> bought
  DELETE /api/gifts/<id>/          delete
  GET    /api/budget/              yearly budget, spent this year, remaining, per person

Only gifts with status "bought" or "given" count as spent.
"""

from flask import Blueprint

budget_bp = Blueprint("budget", __name__)
