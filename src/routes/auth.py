"""
Accounts and login.  Owner: TBD

Planned routes:
  POST /api/register/   create an account {email, password, name}; returns user + tokens
  POST /api/login/      log in {email, password}; returns user + tokens
  POST /api/session/    send the update token as Bearer; returns a fresh session token
  POST /api/logout/     end the current session

See the course's src (4) auth project; User already has the token helpers.
"""

from flask import Blueprint

auth_bp = Blueprint("auth", __name__)
