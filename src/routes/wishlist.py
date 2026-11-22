"""
Wishlists.  Owner: Ziyu

Every user has a wishlist. Friends can see it and claim an item
("I'll get this") so nobody buys the same gift twice.
The owner never sees claims, so the surprise is kept.

Routes (all need a logged-in user):
  GET    /api/wishlist/               my wishlist
  POST   /api/wishlist/               add an item
  PATCH  /api/wishlist/<id>/          edit my item
  DELETE /api/wishlist/<id>/          delete my item
  GET    /api/users/<id>/wishlist/    a friend's wishlist (with claim info)
  POST   /api/wishlist/<id>/claim/    claim a friend's item
  DELETE /api/wishlist/<id>/claim/    take back my claim
"""

from flask import Blueprint

from db import User, WishlistItem, db
from routes.friends import are_friends
from utils import failure_response, get_body, get_current_user, success_response

wishlist_bp = Blueprint("wishlist", __name__)

EDITABLE_FIELDS = ["name", "url", "price", "note"]


# ---------- helpers ----------


def check_price(value):
    """
    Returns an error message if `value` is not a valid price, otherwise None.
    A price may be empty (None) or a number that is 0 or more.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return "price must be a number of 0 or more"
    return None


def get_my_item(user, item_id):
    """
    Finds one of `user`'s own items.
    Returns (item, None), or (None, error_response) if it is missing or not theirs.
    """
    item = WishlistItem.query.filter_by(id=item_id).first()
    if item is None:
        return None, failure_response("Wishlist item not found")
    if item.user_id != user.id:
        return None, failure_response("This is not your wishlist item", 403)
    return item, None


def get_friends_item(user, item_id):
    """
    Finds an item on a friend's wishlist, for claiming.
    Returns (item, None), or (None, error_response) if it can't be claimed.
    """
    item = WishlistItem.query.filter_by(id=item_id).first()
    if item is None:
        return None, failure_response("Wishlist item not found")
    if item.user_id == user.id:
        return None, failure_response("You cannot claim your own wishlist item", 400)
    if not are_friends(user, item.owner):
        return None, failure_response("You can only claim items of your friends", 403)
    return item, None


def items_for(owner, viewer):
    """
    `owner`'s wishlist as `viewer` may see it, newest first
    """
    items = sorted(owner.wishlist_items, key=lambda item: item.created_at, reverse=True)
    return [item.serialize_for(viewer) for item in items]


# ----- my own wishlist ----------


@wishlist_bp.route("/api/wishlist/")
def get_my_wishlist():
    """
    The logged-in user's own wishlist (no claim info)
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)
    return success_response({"items": items_for(user, user)})


@wishlist_bp.route("/api/wishlist/", methods=["POST"])
def add_wishlist_item():
    """
    Adds an item to the logged-in user's wishlist. Only name is required.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    body = get_body()
    if not body.get("name"):
        return failure_response("Missing name", 400)
    price_error = check_price(body.get("price"))
    if price_error:
        return failure_response(price_error, 400)

    item = WishlistItem(
        user_id=user.id,
        name=body.get("name"),
        url=body.get("url"),
        price=body.get("price"),
        note=body.get("note"),
    )
    db.session.add(item)
    db.session.commit()
    return success_response(item.serialize_for(user), 201)


@wishlist_bp.route("/api/wishlist/<int:item_id>/", methods=["PATCH"])
def update_wishlist_item(item_id):
    """
    Edits one of the logged-in user's items; only the fields sent are changed
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    item, error = get_my_item(user, item_id)
    if error:
        return error

    body = get_body()
    if "name" in body and not body["name"]:
        return failure_response("name cannot be empty", 400)
    price_error = check_price(body.get("price"))
    if price_error:
        return failure_response(price_error, 400)

    for field in EDITABLE_FIELDS:
        if field in body:
            setattr(item, field, body[field])
    db.session.commit()
    return success_response(item.serialize_for(user))


@wishlist_bp.route("/api/wishlist/<int:item_id>/", methods=["DELETE"])
def delete_wishlist_item(item_id):
    """
    Deletes one of the logged-in user's items
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    item, error = get_my_item(user, item_id)
    if error:
        return error

    data = item.serialize_for(user)
    db.session.delete(item)
    db.session.commit()
    return success_response(data)


# ---------- friends' wishlists and claims ----------


@wishlist_bp.route("/api/users/<int:owner_id>/wishlist/")
def get_users_wishlist(owner_id):
    """
    Another user's wishlist, with claim info. Friends only.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    owner = User.query.filter_by(id=owner_id).first()
    if owner is None:
        return failure_response("User not found")
    if owner.id != user.id and not are_friends(user, owner):
        return failure_response("You can only see your friends' wishlists", 403)

    return success_response({"owner": owner.simple_serialize(), "items": items_for(owner, user)})


@wishlist_bp.route("/api/wishlist/<int:item_id>/claim/", methods=["POST"])
def claim_item(item_id):
    """
    Claims a friend's wishlist item ("I'll get this").
    The update only succeeds if nobody has claimed it yet, so if two friends
    claim at the same moment, only the first one wins.
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    item, error = get_friends_item(user, item_id)
    if error:
        return error
    if item.claimed_by_id == user.id:
        return failure_response("You already claimed this item", 409)

    # One database statement: "set claimed_by_id = me WHERE it is still empty".
    # rows_changed is 0 if someone else got there first.
    rows_changed = WishlistItem.query.filter_by(id=item.id, claimed_by_id=None).update(
        {"claimed_by_id": user.id}
    )
    db.session.commit()
    if rows_changed == 0:
        return failure_response("Someone already claimed this item", 409)

    db.session.refresh(item)
    return success_response(item.serialize_for(user))


@wishlist_bp.route("/api/wishlist/<int:item_id>/claim/", methods=["DELETE"])
def unclaim_item(item_id):
    """
    Takes back the logged-in user's own claim on an item
    """
    user = get_current_user()
    if user is None:
        return failure_response("Invalid or expired session token", 401)

    item = WishlistItem.query.filter_by(id=item_id).first()
    if item is None:
        return failure_response("Wishlist item not found")
    if item.claimed_by_id != user.id:
        return failure_response("You have not claimed this item", 403)

    item.claimed_by_id = None
    db.session.commit()
    return success_response(item.serialize_for(user))
