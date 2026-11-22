"""
Database models for the gift app.
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

    # friend card 
    name = db.Column(db.String, nullable=False)
    birth_month = db.Column(db.Integer, nullable=False)  # 1-12
    birth_day = db.Column(db.Integer, nullable=False)  # 1-31
    birth_year = db.Column(db.Integer, nullable=True)  # optional
    mbti = db.Column(db.String, nullable=True)  # e.g. "INTJ"
    hobbies = db.Column(db.String, nullable=True)  # e.g. "Photography, tea"
    additional_info = db.Column(db.Text, nullable=True)
    yearly_budget = db.Column(db.Float, nullable=False, default=0)

    # session 
    session_token = db.Column(db.String, nullable=False, unique=True)
    session_expiration = db.Column(db.DateTime, nullable=False)
    update_token = db.Column(db.String, nullable=False, unique=True)

    # 3. Relationships
    # --- Ziyu ---
    # contacts this user saved (manual or linked to a friend's account)
    people = db.relationship(
        "Person", foreign_keys="Person.user_id", back_populates="owner", cascade="delete"
    )
    # this user's own wishlist
    wishlist_items = db.relationship(
        "WishlistItem",
        foreign_keys="WishlistItem.user_id",
        back_populates="owner",
        cascade="delete",
    )

    # --- Alya ---

    def __init__(self, **kwargs):
        """
        Creates a user with a hashed password and a fresh session
        """
        self.email = kwargs.get("email")
        self.name = kwargs.get("name")
        self.birth_month = kwargs.get("birth_month")
        self.birth_day = kwargs.get("birth_day")
        self.birth_year = kwargs.get("birth_year")
        self.mbti = kwargs.get("mbti")
        self.hobbies = kwargs.get("hobbies")
        self.additional_info = kwargs.get("additional_info")
        self.yearly_budget = kwargs.get("yearly_budget", 0)
        self.password_digest = bcrypt.hashpw(
            kwargs.get("password").encode("utf8"), bcrypt.gensalt(rounds=13)
        )
        self.renew_session()

    # Helper methods

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

    # JSON

    def serialize(self):
        """
        The user's full friend card (never includes the password or tokens)
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "birth_month": self.birth_month,
            "birth_day": self.birth_day,
            "birth_year": self.birth_year,
            "mbti": self.mbti,
            "hobbies": self.hobbies,
            "additional_info": self.additional_info,
            "yearly_budget": round(self.yearly_budget, 2),
        }

    def simple_serialize(self):
        """
        Short version, used when a user appears inside another object
        """
        return {"id": self.id, "name": self.name}



class Person(db.Model):
    """
    A contact saved by a user: either created by hand (a friend who is not on
    the app) or created automatically when two users become friends
    (linked_user_id points to the friend's account).
    Gifts and per-person budgets attach to a Person.
    """

    __tablename__ = "person"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    linked_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    name = db.Column(db.String, nullable=False)
    birth_month = db.Column(db.Integer, nullable=False)
    birth_day = db.Column(db.Integer, nullable=False)
    birth_year = db.Column(db.Integer, nullable=True)
    mbti = db.Column(db.String, nullable=True)
    hobbies = db.Column(db.String, nullable=True)
    additional_info = db.Column(db.Text, nullable=True)

    budget = db.Column(db.Float, nullable=True)
    relationship = db.Column(db.String, nullable=True)  # "friend", "family"...

    owner = db.relationship("User", foreign_keys=[user_id], back_populates="people")
    linked_user = db.relationship("User", foreign_keys=[linked_user_id])
    gifts = db.relationship("Gift", back_populates="person", cascade="delete")

    # Helpers
    def profile(self):
        """
        The profile fields to show. For a linked contact they come from the
        friend's own account, so they stay up to date.
        """
        source = self.linked_user if self.linked_user is not None else self
        return {
            "name": source.name,
            "birth_month": source.birth_month,
            "birth_day": source.birth_day,
            "birth_year": source.birth_year,
            "mbti": source.mbti,
            "hobbies": source.hobbies,
            "additional_info": source.additional_info,
        }

    def serialize(self):
        return {
            "id": self.id,
            "linked_user_id": self.linked_user_id,
            **self.profile(),
            "budget": round(self.budget, 2) if self.budget is not None else None,
            "relationship": self.relationship,
            "gifts": [gift.simple_serialize() for gift in self.gifts],
        }

    def simple_serialize(self):
        info = self.profile()
        return {
            "id": self.id,
            "name": info["name"],
            "birth_month": info["birth_month"],
            "birth_day": info["birth_day"],
        }


class Relationship(db.Model):
    """
    A friendship between two users. 
    One user is the requester for this relationship,
    One user is the addressee for this relationship.
    """

    __tablename__ = "relationship"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String, nullable=False, default= "pending")
    created_at = db.Column(db.DateTime, nullable= False, default= datetime.datetime.now)
    
    requester = db.relationship("User", foreign_keys=[requester_id])
    addressee = db.relationship("User", foreign_keys= [addressee_id])

    __table_args__ = (
        db.UniqueConstraint("requester_id", "addressee_id", name="unique_relationship"),
    )

    #helpers
    def other_user(self, user):
        """Given a 'user' in this relationship, return the other side of this relationship."""
        if user.id == self.requester_id:
            return self.addressee
        return self.requester

    def involves(self, user):
        """check if the 'user' is in this relationship"""
        return user.id == self.requester_id or user.id == self.addressee_id

    def serialize(self):
        return {
            "id": self.id,
            "requester": self.requester.simple_serialize(),
            "addressee": self.addressee.simple_serialize(),
            "status": self.status,
        }


GIFT_STATUSES = ["idea", "bought", "given"]


class Gift(db.Model):
    """
    A gift idea or purchase for one of the user's contacts.
    Only "bought" and "given" gifts count as money spent.
    """

    __tablename__ = "gift"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    name = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=True)
    status = db.Column(db.String, nullable=False, default="idea")
    url = db.Column(db.String, nullable=True)
    date = db.Column(db.Date, nullable=True)  # when it was bought or given
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)

    person = db.relationship("Person", back_populates="gifts")

    def simple_serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "price": round(self.price, 2) if self.price is not None else None,
            "status": self.status,
            "url": self.url,
            "date": date_to_str(self.date),
        }

    def serialize(self):
        data = self.simple_serialize()
        data["person"] = self.person.simple_serialize()
        return data


class WishlistItem(db.Model):
    """
    Something a user wants. Friends can claim an item ("I'll get this") so
    nobody buys it twice; the owner never sees claims.
    """

    __tablename__ = "wishlist_item"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String, nullable=False)
    url = db.Column(db.String, nullable=True)
    price = db.Column(db.Float, nullable=True)
    note = db.Column(db.String, nullable=True)
    claimed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)

    owner = db.relationship(
        "User", foreign_keys=[user_id], back_populates="wishlist_items"
    )
    claimed_by = db.relationship("User", foreign_keys=[claimed_by_id])

    def serialize_for(self, viewer):
        """
        The item as `viewer` may see it. The owner gets no claim info;
        anyone else sees "claim": null (free), "by_you" or "by_someone".
        """
        data = {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "price": round(self.price, 2) if self.price is not None else None,
            "note": self.note,
        }
        if viewer.id != self.user_id:
            if self.claimed_by_id is None:
                data["claim"] = None
            elif self.claimed_by_id == viewer.id:
                data["claim"] = "by_you"
            else:
                data["claim"] = "by_someone"
        return data


# SpecialDay    a festival (user_id empty) or a personal date
#               user_id (FK -> user, nullable), name, date
#               User -> SpecialDay is one-to-many

# Event         a group celebration
#               host_id (FK -> user), title, starts_at, location, description
#               User -> Event (host) is one-to-many

# Invitation  association table: event_id + user_id
#               Event <-> User (guests) is many-to-many
