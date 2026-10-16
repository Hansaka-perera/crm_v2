from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="sales")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles) -> bool:
        return self.role in roles

    def can_manage_all(self) -> bool:
        return self.role in ("admin", "manager")


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    address = db.Column(db.String(255), default="")
    website = db.Column(db.String(255), default="")
    phone = db.Column(db.String(64), default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", backref="organizations")
    people = db.relationship("Person", backref="organization", lazy="dynamic")
    deals = db.relationship("Deal", backref="organization", lazy="dynamic")


class Person(db.Model):
    __tablename__ = "people"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    email = db.Column(db.String(255), index=True, default="")
    phone = db.Column(db.String(64), default="")
    job_title = db.Column(db.String(120), default="")
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", backref="people")
    deals = db.relationship("Deal", backref="person", lazy="dynamic")


class Deal(db.Model):
    __tablename__ = "deals"

    STAGES = (
        "Qualified",
        "Demo Scheduled",
        "Demo Completed",
        "Proposal Made",
        "Negotiations",
        "Contract Signed",
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    value = db.Column(db.Float, default=0)
    currency = db.Column(db.String(8), default="LKR")
    stage = db.Column(db.String(64), default="Qualified", index=True)
    status = db.Column(db.String(32), default="open", index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    expected_close_date = db.Column(db.Date)
    next_activity_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", backref="deals")


class Lead(db.Model):
    __tablename__ = "leads"

    STATUSES = ("new", "contacted", "qualified", "converted", "lost")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    person_name = db.Column(db.String(200), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(64), default="")
    organization_name = db.Column(db.String(200), default="")
    source = db.Column(db.String(80), default="manual")
    status = db.Column(db.String(32), default="new", index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", backref="leads")
    person = db.relationship("Person")
    organization = db.relationship("Organization")


class Activity(db.Model):
    __tablename__ = "activities"

    TYPES = ("call", "meeting", "task", "deadline", "email", "lunch")

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(32), nullable=False, default="task")
    subject = db.Column(db.String(255), nullable=False)
    due_at = db.Column(db.DateTime)
    done = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text, default="")
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", backref="activities")
    person = db.relationship("Person", backref="activities")
    organization = db.relationship("Organization", backref="activities")
    deal = db.relationship("Deal", backref="activities")


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    author = db.relationship("User")
    person = db.relationship("Person", backref="notes")
    organization = db.relationship("Organization", backref="notes")
    deal = db.relationship("Deal", backref="notes")


class InboxMessage(db.Model):
    __tablename__ = "inbox_messages"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default="")
    from_email = db.Column(db.String(255), default="")
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    person = db.relationship("Person")
    owner = db.relationship("User")


class CustomerRequest(db.Model):
    __tablename__ = "customer_requests"

    STATUSES = ("new", "assigned", "approved", "rejected", "completed")

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(80), index=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False, index=True)
    customer_phone = db.Column(db.String(64), default="")
    organization_name = db.Column(db.String(200), default="")
    request_type = db.Column(db.String(80), default="support")
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(32), default="new", index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    assigned_to = db.relationship("User")
    person = db.relationship("Person")
    organization = db.relationship("Organization")


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    prefix = db.Column(db.String(12), nullable=False, index=True)
    key_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime)

    created_by = db.relationship("User")


class WebForm(db.Model):
    __tablename__ = "web_forms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
