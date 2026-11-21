"""
My profile (friend card) from the questionnaire.  Owner: TBD

Planned routes:
  GET   /api/me/          my full friend card
  PATCH /api/me/          save questionnaire answers (birthday, interests, yearly_budget...)
  GET   /api/users/<id>/  another user's friend card (full only if we are friends)
"""

from flask import Blueprint

profile_bp = Blueprint("profile", __name__)
