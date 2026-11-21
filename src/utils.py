"""
Shared helpers used by every route file.
"""

import json

from flask import request

from db import User


def success_response(data, code=200):
    """
    Returns a JSON success response with the given data and status code
    """
    return json.dumps(data), code


def failure_response(message, code=404):
    """
    Returns a JSON error response with the given message and status code
    """
    return json.dumps({"error": message}), code


def get_body():
    """
    Parses the JSON request body, returning an empty dict if it is
    missing or not valid JSON
    """
    try:
        body = json.loads(request.data)
    except (TypeError, ValueError):
        return {}
    if not isinstance(body, dict):
        return {}
    return body


def get_current_user():
    """
    Reads the "Authorization: Bearer <session_token>" header and returns
    the logged-in User, or None if the token is missing, unknown or expired.

    Start every protected route with:

        user = get_current_user()
        if user is None:
            return failure_response("Invalid or expired session token", 401)
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):].strip()
    user = User.query.filter_by(session_token=token).first()
    if user is None or not user.verify_session_token(token):
        return None
    return user
