"""
Wishlists.  Owner: TBD

Planned routes:
  GET    /api/wishlist/              my wishlist
  POST   /api/wishlist/              add an item {name, url, price, note}
  PATCH  /api/wishlist/<id>/         edit my item
  DELETE /api/wishlist/<id>/         delete my item
  GET    /api/users/<id>/wishlist/   a friend's wishlist (friends only)
"""

from flask import Blueprint

wishlist_bp = Blueprint("wishlist", __name__)
