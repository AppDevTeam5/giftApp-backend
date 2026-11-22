"""
Friends between app users. Owner: Ziyu 

Planned routes:
  GET    /api/users/search/?q=...             find users by name or email
  POST   /api/friends/requests/               send a request {user_id}
  GET    /api/friends/requests/               my pending requests (sent and received)
  POST   /api/friends/requests/<id>/accept/   accept
  POST   /api/friends/requests/<id>/decline/  decline
  GET    /api/friends/                        my friends
  DELETE /api/friends/<user_id>/              remove a friend
"""

from flask import Blueprint, request
from sqlalchemy import and_, or_

from db import Person, Relationship, User, WishlistItem, db
from utils import failure_response, get_body, get_current_user, success_response

friends_bp = Blueprint("friends", __name__)


# ---------- helper functions ----------


def find_relationship(user_a, user_b):
    """
    Returns the relationship row between two users in either direction,
    or None if there is none
    """
    return Relationship.query.filter(
        or_(
            and_(Relationship.requester_id == user_a.id, Relationship.addressee_id == user_b.id),
            and_(Relationship.requester_id == user_b.id, Relationship.addressee_id == user_a.id),
        )
    ).first()


def are_friends(user_a, user_b):
    """
    True only if the two users have a relationship row with status = "accepted"
    """
    row = find_relationship(user_a, user_b)
    return row is not None and row.status == "accepted"


def get_friends(user):
    """
    Returns a list of every user this user has an accepted relationship with
    """
    rows = Relationship.query.filter(
        or_(Relationship.requester_id == user.id, Relationship.addressee_id == user.id),
        Relationship.status == "accepted",
    ).all()
    return [row.other_user(user) for row in rows]


def friend_status(user, other):
    """
    How `other` relates to `user`, for showing the right button in the app:
    "friends", "request_sent", "request_received", or None
    """
    row = find_relationship(user, other)
    if row is None:
        return None
    if row.status == "accepted":
        return "friends"
    if row.requester_id == user.id:
        return "request_sent"
    return "request_received"


def link_contact(owner, friend):
    """
    Makes sure `owner` has a contact (Person) linked to `friend`'s account.
    1. Already linked -> use it.
    2. An unlinked contact with the same name and birthday (saved by hand, or
       left over from an earlier friendship) -> link it, keeping its gifts.
    3. Otherwise create a new one. The profile fields are copied so the
       contact still has them if the friendship ends later.
    """
    contact = Person.query.filter_by(user_id=owner.id, linked_user_id=friend.id).first()
    if contact is not None:
        return contact

    contact = Person.query.filter_by(
        user_id=owner.id,
        linked_user_id=None,
        name=friend.name,
        birth_month=friend.birth_month,
        birth_day=friend.birth_day,
    ).first()
    if contact is not None:
        contact.linked_user_id = friend.id
        return contact

    contact = Person(
        user_id=owner.id,
        linked_user_id=friend.id,
        name=friend.name,
        birth_month=friend.birth_month,
        birth_day=friend.birth_day,
        birth_year=friend.birth_year,
        mbti=friend.mbti,
        hobbies=friend.hobbies,
        additional_info=friend.additional_info,
        relationship="friend",
    )
    db.session.add(contact)
    return contact


def unlink_contact(owner, friend):
    """
    Turns `owner`'s linked contact for `friend` into a normal manual contact,
    keeping its gifts and budget. The friend's latest profile is copied in first.
    """
    contact = Person.query.filter_by(user_id=owner.id, linked_user_id=friend.id).first()
    if contact is None:
        return
    contact.name = friend.name
    contact.birth_month = friend.birth_month
    contact.birth_day = friend.birth_day
    contact.birth_year = friend.birth_year
    contact.mbti = friend.mbti
    contact.hobbies = friend.hobbies
    contact.additional_info = friend.additional_info
    contact.linked_user_id = None


def release_claims(claimer, owner):
    """
    Removes every claim `claimer` made on `owner`'s wishlist
    (used when they stop being friends)
    """
    WishlistItem.query.filter_by(user_id=owner.id, claimed_by_id=claimer.id).update(
        {"claimed_by_id": None}
    )


def get_pending_request(user, request_id):
    """
    Finds a pending request that `user` received.
    Returns (row, None) if allowed, or (None, error_response) if not.
    """
    row = Relationship.query.filter_by(id=request_id).first()
    if row is None:
        return None, failure_response("Friend request not found")
    if row.addressee_id != user.id:
        return None, failure_response("Only the receiver can answer this request", 403)
    if row.status != "pending":
        return None, failure_response("This request was already answered", 400)
    return row, None


# ----routes ----
@friends_bp.route("/api/friends/requests/", methods=["POST"])
def send_friend_request():
    """
    Sends a friend request from the logged-in user to another user
    """
    # Logged in?
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    # Read the body
    body = get_body()
    other_id = body.get("user_id")
    if other_id is None:
        return failure_response("Missing user_id", 400)

    # Not yourself
    if other_id == user.id:
        return failure_response("You cannot add yourself as a friend", 400)

    # Check whether the other user exists
    other = User.query.filter_by(id=other_id).first()
    if other is None:
        return failure_response("User not found")

    # Check if there's already a row between them
    existing = find_relationship(user, other)
    if existing is not None:
        if existing.status == "accepted":
            return failure_response("You are already friends", 409)
        if existing.requester_id == user.id:
            return failure_response("Friend request already sent", 409)
        return failure_response("This user already sent you a request. Accept it instead.", 409)

    # All checks passed--> create the row
    new_relationship= Relationship(requester_id=user.id, addressee_id=other.id)
    db.session.add(new_relationship)
    db.session.commit()
    return success_response(new_relationship.serialize(), 201)

@friends_bp.route("/api/friends/requests/")
def get_friend_requests():
    """
    Returns the logged-in user's pending requests, received and sent
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    sent = Relationship.query.filter_by(requester_id=user.id, status="pending").all()
    received = Relationship.query.filter_by(addressee_id=user.id, status="pending").all()

    return success_response({
        "received": [row.serialize() for row in received],
        "sent": [row.serialize() for row in sent],
    })


@friends_bp.route("/api/friends/requests/<int:request_id>/accept/", methods=["POST"])
def accept_friend_request(request_id):
    """
    Accepts a request the logged-in user received; both users get a linked contact
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    row, error = get_pending_request(user, request_id)
    if error:
        return error

    row.status = "accepted"
    link_contact(row.requester, row.addressee)
    link_contact(row.addressee, row.requester)
    db.session.commit()
    return success_response(row.serialize())


@friends_bp.route("/api/friends/requests/<int:request_id>/decline/", methods=["POST"])
def decline_friend_request(request_id):
    """
    Declines a request the logged-in user received. The row is deleted,
    so the other user can send a new request later.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    row, error = get_pending_request(user, request_id)
    if error:
        return error

    db.session.delete(row)
    db.session.commit()
    return success_response({"message": "Friend request declined"})


@friends_bp.route("/api/friends/")
def list_friends():
    """
    The logged-in user's friends, with the id of the linked contact
    (used to open their gifts and budget)
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    friends = []
    for friend in get_friends(user):
        contact = Person.query.filter_by(user_id=user.id, linked_user_id=friend.id).first()
        friends.append(
            {
                "id": friend.id,
                "name": friend.name,
                "birth_month": friend.birth_month,
                "birth_day": friend.birth_day,
                "person_id": contact.id if contact is not None else None,
            }
        )
    friends.sort(key=lambda f: f["name"].lower())
    return success_response({"friends": friends})


@friends_bp.route("/api/friends/<int:friend_id>/", methods=["DELETE"])
def remove_friend(friend_id):
    """
    Ends a friendship. Both linked contacts become manual contacts,
    keeping their gifts and budgets, and any claims either user made on the
    other's wishlist are released.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    friend = User.query.filter_by(id=friend_id).first()
    if friend is None:
        return failure_response("User not found")
    row = find_relationship(user, friend)
    if row is None or row.status != "accepted":
        return failure_response("You are not friends with this user")

    db.session.delete(row)
    unlink_contact(user, friend)
    unlink_contact(friend, user)
    release_claims(user, friend)
    release_claims(friend, user)
    db.session.commit()
    return success_response({"message": "Friend removed"})


@friends_bp.route("/api/users/search/")
def search_users():
    """
    Finds users by name or email (?q=...). Returns only public info,
    plus how each result relates to the logged-in user.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    query = request.args.get("q", "").strip()
    if not query:
        return failure_response("Missing search text q", 400)

    pattern = "%" + query + "%"
    results = (
        User.query.filter(
            or_(User.name.ilike(pattern), User.email.ilike(pattern)),
            User.id != user.id,
        )
        .limit(20)
        .all()
    )
    return success_response(
        {
            "users": [
                {**other.simple_serialize(), "friend_status": friend_status(user, other)}
                for other in results
            ]
        }
    )
