"""
Group celebration events.  Owner: TBD

Planned routes:
  GET    /api/events/                    events I host or am a guest at
  POST   /api/events/                    create {title, starts_at, location, description}
  GET    /api/events/<id>/               one event (host and guests only)
  PATCH  /api/events/<id>/               edit (host only)
  DELETE /api/events/<id>/               delete (host only)
  POST   /api/events/<id>/guests/        add a guest {user_id} (host only, friends only)
  DELETE /api/events/<id>/guests/<uid>/  remove a guest (host only)
"""

from flask import Blueprint

events_bp = Blueprint("events", __name__)
