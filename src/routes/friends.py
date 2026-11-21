"""
Friends between app users.  Owner: TBD

Planned routes:
  GET    /api/users/search/?q=...             find users by name or email
  POST   /api/friends/requests/               send a request {user_id}
  GET    /api/friends/requests/               my pending requests (sent and received)
  POST   /api/friends/requests/<id>/accept/   accept
  POST   /api/friends/requests/<id>/decline/  decline
  GET    /api/friends/                        my friends
  DELETE /api/friends/<user_id>/              remove a friend
"""

from flask import Blueprint

friends_bp = Blueprint("friends", __name__)
