"""
Database models for the gift app.

User is written in full as the TEMPLATE. Copy its pattern for every other model:
  1. __tablename__
  2. columns  (db.Column, with nullable / unique / ForeignKey)
  3. relationships  (db.relationship, with back_populates and cascade)
  4. helper methods, if any
  5. serialize()  (full JSON)  and  simple_serialize()  (short JSON for nesting)
"""

import datetime
import hashlib
import os

import bcrypt
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def date_to_str(value):
    """
    Turns a date into "YYYY-MM-DD" text for JSON (None stays None)
    """
    return value.isoformat() if value is not None else None


# =====================================================================
# TEMPLATE MODEL
# =====================================================================


class User(db.Model):
    """
    An account plus the user's own profile ("friend card"),
    filled in from the sign-up questionnaire
    """

    # 1. Table name
    __tablename__ = "user"

    # 2. Columns
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # login
    email = db.Column(db.String, nullable=False, unique=True)
    password_digest = db.Column(db.String, nullable=False)

    # friend card (questionnaire answers)
    name = db.Column(db.String, nullable=False)
    birthday = db.Column(db.Date, nullable=True)
    interests = db.Column(db.String, nullable=True)
    yearly_budget = db.Column(db.Float, nullable=False, default=0)

    # session (from the course's authentication demo)
    session_token = db.Column(db.String, nullable=False, unique=True)
    session_expiration = db.Column(db.DateTime, nullable=False)
    update_token = db.Column(db.String, nullable=False, unique=True)

    # 3. Relationships
    #    Add one line here for each model that points back to User, e.g.:
    #    people = db.relationship("Person", back_populates="user", cascade="delete")

    def __init__(self, **kwargs):
        """
        Creates a user with a hashed password and a fresh session
        """
        self.email = kwargs.get("email")
        self.name = kwargs.get("name")
        self.password_digest = bcrypt.hashpw(
            kwargs.get("password").encode("utf8"), bcrypt.gensalt(rounds=13)
        )
        self.renew_session()

    # 4. Helper methods

    def _urlsafe_base_64(self):
        """
        Randomly generates a token
        """
        return hashlib.sha1(os.urandom(64)).hexdigest()

    def renew_session(self):
        """
        Creates a new session token (valid for one day) and a new update token
        """
        self.session_token = self._urlsafe_base_64()
        self.session_expiration = datetime.datetime.now() + datetime.timedelta(days=1)
        self.update_token = self._urlsafe_base_64()

    def verify_password(self, password):
        return bcrypt.checkpw(password.encode("utf8"), self.password_digest)

    def verify_session_token(self, session_token):
        return (
            session_token == self.session_token
            and datetime.datetime.now() < self.session_expiration
        )

    def verify_update_token(self, update_token):
        return update_token == self.update_token

    # 5. JSON

    def serialize(self):
        """
        The user's full friend card (never includes the password or tokens)
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "birthday": date_to_str(self.birthday),
            "interests": self.interests,
            "yearly_budget": round(self.yearly_budget, 2),
        }

    def simple_serialize(self):
        """
        Short version, used when a user appears inside another object
        """
        return {"id": self.id, "name": self.name}


# =====================================================================
# TODO: models to write, following the User template above
# =====================================================================
#
# Person        a friend saved manually (not on the app)
#               user_id (FK -> user), name, birthday, budget, relationship, notes
#               User -> Person is one-to-many
#
# Gift          a gift idea or purchase for a saved person
#               person_id (FK -> person), name, price, status ("idea"/"bought"/"given"), url, date
#               Person -> Gift is one-to-many
#
# WishlistItem  something a user wants
#               user_id (FK -> user), name, url, price, note
#               User -> WishlistItem is one-to-many
#
# SpecialDay    a festival (user_id empty) or a personal date
#               user_id (FK -> user, nullable), name, date
#               User -> SpecialDay is one-to-many
#
# Friendship    a connection between two users
#               requester_id (FK -> user), addressee_id (FK -> user), status ("pending"/"accepted")
#               User <-> User is many-to-many; two FKs point at user, so each
#               db.relationship needs foreign_keys=[...]
#
# Event         a group celebration
#               host_id (FK -> user), title, starts_at, location, description
#               User -> Event (host) is one-to-many
#
# event_guests  association table: event_id + user_id
#               Event <-> User (guests) is many-to-many
