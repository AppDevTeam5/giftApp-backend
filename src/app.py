"""
Entry point of the backend: creates the Flask app, connects the database
and registers the route files in routes/.

Run locally:  python app.py   (then open http://localhost:8000/)
"""

import os

from dotenv import load_dotenv
from flask import Flask

from db import db
from routes.auth import auth_bp
from routes.budget import budget_bp
from routes.dates import dates_bp
from routes.events import events_bp
from routes.friends import friends_bp
from routes.people import people_bp
from routes.profile import profile_bp
from routes.suggestions import suggestions_bp
from routes.wishlist import wishlist_bp
from utils import success_response

load_dotenv()

app = Flask(__name__)
db_filename = os.environ.get("DATABASE_FILE", "giftapp.db")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///%s" % db_filename
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = os.environ.get("SQL_ECHO") == "1"

db.init_app(app)
with app.app_context():
    db.create_all()

# Each file in routes/ is a "blueprint": a group of related routes
for blueprint in [
    auth_bp,
    profile_bp,
    friends_bp,
    wishlist_bp,
    people_bp,
    dates_bp,
    budget_bp,
    events_bp,
    suggestions_bp,
]:
    app.register_blueprint(blueprint)


@app.route("/")
def health_check():
    """
    Quick check that the server is running
    """
    return success_response({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
