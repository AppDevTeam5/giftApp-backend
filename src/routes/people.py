"""
Friends saved manually (people not on the app).  Owner: TBD

Planned routes:
  GET    /api/people/        my saved people
  POST   /api/people/        add {name, birthday, budget, relationship, notes}
  GET    /api/people/<id>/   one person with their gifts
  PATCH  /api/people/<id>/   edit
  DELETE /api/people/<id>/   delete (their gifts are deleted too)
"""

from flask import Blueprint

people_bp = Blueprint("people", __name__)
