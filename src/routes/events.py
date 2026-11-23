"""
Group celebration events and invitations.  Owner: Alya

Routes:
  GET    /api/events/                           events I host or accepted
  POST   /api/events/                           create {title, starts_at, location, description}
  GET    /api/events/<id>/                      one event (host and invited users only)
  PATCH  /api/events/<id>/                      edit (host only)
  DELETE /api/events/<id>/                      delete (host only)
  POST   /api/events/<id>/invitations/          invite a friend {user_id} (host only)
  DELETE /api/events/<id>/invitations/<uid>/    cancel an invitation / remove a guest (host only)
  GET    /api/invitations/?status=pending       invitations I received
  POST   /api/invitations/<id>/accept/          say yes (I become a guest)
  POST   /api/invitations/<id>/decline/         say no (also works to leave after accepting)

The guests of an event are the users who accepted their invitation.
starts_at is sent as "YYYY-MM-DDTHH:MM:SS".
"""

import datetime

from flask import Blueprint, request

from db import INVITATION_STATUSES, Event, Invitation, User, db
from routes.friends import are_friends
from utils import failure_response, get_body, get_current_user, success_response

events_bp = Blueprint("events", __name__)

EDITABLE_FIELDS = ["title", "starts_at", "location", "description"]


# ---------- helper functions ----------


def parse_starts_at(value):
    """
    Turns "YYYY-MM-DDTHH:MM:SS" text into a datetime, or None if invalid
    """
    try:
        return datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def find_invitation(event, user):
    """
    Returns `user`'s invitation to `event`, or None
    """
    return Invitation.query.filter_by(event_id=event.id, receiver_id=user.id).first()


def get_visible_event(user, event_id):
    """
    Finds an event that `user` may see: they host it or were invited.
    Returns (event, None) if allowed, or (None, error_response) if not.
    """
    event = Event.query.filter_by(id=event_id).first()
    if event is None:
        return None, failure_response("Event not found")
    if event.host_id != user.id and find_invitation(event, user) is None:
        return None, failure_response("You are not part of this event", 403)
    return event, None


def get_my_event(user, event_id):
    """
    Finds an event that `user` hosts.
    Returns (event, None) if allowed, or (None, error_response) if not.
    """
    event = Event.query.filter_by(id=event_id).first()
    if event is None:
        return None, failure_response("Event not found")
    if event.host_id != user.id:
        return None, failure_response("Only the host can do this", 403)
    return event, None


def get_my_invitation(user, invitation_id):
    """
    Finds an invitation that `user` received.
    Returns (invitation, None) if allowed, or (None, error_response) if not.
    """
    invitation = Invitation.query.filter_by(id=invitation_id).first()
    if invitation is None:
        return None, failure_response("Invitation not found")
    if invitation.receiver_id != user.id:
        return None, failure_response("Only the receiver can answer this invitation", 403)
    return invitation, None


# ---------- events ----------


@events_bp.route("/api/events/")
def get_events():
    """
    Returns the events the logged-in user hosts and the ones they accepted
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    going = [
        invitation.event
        for invitation in user.invitations
        if invitation.status == "accepted"
    ]
    hosting = sorted(user.hosted_events, key=lambda event: event.starts_at)
    going.sort(key=lambda event: event.starts_at)
    return success_response(
        {
            "hosting": [event.simple_serialize() for event in hosting],
            "going": [event.simple_serialize() for event in going],
        }
    )


@events_bp.route("/api/events/", methods=["POST"])
def create_event():
    """
    Creates an event hosted by the logged-in user.
    title and starts_at are required; location and description are optional.
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Read the body
    body = get_body()
    title = body.get("title")
    if not title or body.get("starts_at") is None:
        return failure_response("Missing title or starts_at", 400)

    # Check the date-time
    starts_at = parse_starts_at(body.get("starts_at"))
    if starts_at is None:
        return failure_response("starts_at must be YYYY-MM-DDTHH:MM:SS", 400)

    # All checks passed --> create the row
    event = Event(
        host_id=user.id,
        title=title,
        starts_at=starts_at,
        location=body.get("location"),
        description=body.get("description"),
    )
    db.session.add(event)
    db.session.commit()
    return success_response(event.serialize(), 201)


@events_bp.route("/api/events/<int:event_id>/")
def get_event(event_id):
    """
    Returns one event with its invitations (host and invited users only)
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Can this user see it?
    event, error = get_visible_event(user, event_id)
    if error is not None:
        return error
    return success_response(event.serialize())


@events_bp.route("/api/events/<int:event_id>/", methods=["PATCH"])
def update_event(event_id):
    """
    Edits an event. Only the fields that are sent are changed (host only).
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Is this user the host?
    event, error = get_my_event(user, event_id)
    if error is not None:
        return error

    # Check the new values before changing anything
    body = get_body()
    if "title" in body and not body["title"]:
        return failure_response("title cannot be empty", 400)
    starts_at = None
    if "starts_at" in body:
        starts_at = parse_starts_at(body["starts_at"])
        if starts_at is None:
            return failure_response("starts_at must be YYYY-MM-DDTHH:MM:SS", 400)

    # All checks passed --> update the fields that were sent
    for field in EDITABLE_FIELDS:
        if field in body:
            setattr(event, field, starts_at if field == "starts_at" else body[field])
    db.session.commit()
    return success_response(event.serialize())


@events_bp.route("/api/events/<int:event_id>/", methods=["DELETE"])
def delete_event(event_id):
    """
    Deletes an event and its invitations (host only)
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Is this user the host?
    event, error = get_my_event(user, event_id)
    if error is not None:
        return error

    data = event.simple_serialize()
    db.session.delete(event)
    db.session.commit()
    return success_response(data)


# ---------- invitations ----------


@events_bp.route("/api/events/<int:event_id>/invitations/", methods=["POST"])
def invite_to_event(event_id):
    """
    The host invites one of their friends to the event.
    Inviting someone who declined before sends the invitation again.
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Is this user the host?
    event, error = get_my_event(user, event_id)
    if error is not None:
        return error

    # Read the body
    body = get_body()
    other_id = body.get("user_id")
    if other_id is None:
        return failure_response("Missing user_id", 400)

    # Not yourself
    if other_id == user.id:
        return failure_response("You are already the host", 400)

    # Check whether the other user exists and is a friend
    other = User.query.filter_by(id=other_id).first()
    if other is None:
        return failure_response("User not found")
    if not are_friends(user, other):
        return failure_response("You can only invite your friends", 403)

    # Already invited?
    invitation = find_invitation(event, other)
    if invitation is not None:
        if invitation.status != "declined":
            return failure_response("This user is already invited", 409)
        invitation.status = "pending"
        db.session.commit()
        return success_response(invitation.simple_serialize())

    # All checks passed --> create the row
    invitation = Invitation(event_id=event.id, receiver_id=other.id)
    db.session.add(invitation)
    db.session.commit()
    return success_response(invitation.simple_serialize(), 201)


@events_bp.route("/api/events/<int:event_id>/invitations/<int:other_id>/", methods=["DELETE"])
def remove_invitation(event_id, other_id):
    """
    The host cancels someone's invitation (removes them as a guest if they accepted)
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Is this user the host?
    event, error = get_my_event(user, event_id)
    if error is not None:
        return error

    # Was this user invited?
    invitation = Invitation.query.filter_by(event_id=event.id, receiver_id=other_id).first()
    if invitation is None:
        return failure_response("This user is not invited")

    data = invitation.simple_serialize()
    db.session.delete(invitation)
    db.session.commit()
    return success_response(data)


@events_bp.route("/api/invitations/")
def get_my_invitations():
    """
    Returns the invitations the logged-in user received, newest event first.
    ?status=pending (or accepted / declined) filters them.
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Read ?status=
    status = request.args.get("status")
    if status is not None and status not in INVITATION_STATUSES:
        return failure_response("status must be pending, accepted or declined", 400)

    invitations = [
        invitation
        for invitation in user.invitations
        if status is None or invitation.status == status
    ]
    invitations.sort(key=lambda invitation: invitation.event.starts_at)
    return success_response(
        {"invitations": [invitation.serialize() for invitation in invitations]}
    )


@events_bp.route("/api/invitations/<int:invitation_id>/accept/", methods=["POST"])
def accept_invitation(invitation_id):
    """
    Accepts an invitation: the user becomes a guest of the event
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Is it this user's invitation?
    invitation, error = get_my_invitation(user, invitation_id)
    if error is not None:
        return error

    invitation.status = "accepted"
    db.session.commit()
    return success_response(invitation.serialize())


@events_bp.route("/api/invitations/<int:invitation_id>/decline/", methods=["POST"])
def decline_invitation(invitation_id):
    """
    Declines an invitation. Also used to leave an event after accepting.
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Is it this user's invitation?
    invitation, error = get_my_invitation(user, invitation_id)
    if error is not None:
        return error

    invitation.status = "declined"
    db.session.commit()
    return success_response(invitation.serialize())
