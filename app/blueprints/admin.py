import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.helpers import roles_required
from app.models import ApiKey, User

bp = Blueprint("admin", __name__)


@bp.route("/settings/users")
@login_required
@roles_required("admin")
def users():
    return render_template(
        "admin/users.html",
        users=User.query.order_by(User.name).all(),
        section="settings",
        subsection="users",
    )


@bp.route("/settings/users/new", methods=["POST"])
@login_required
@roles_required("admin")
def user_new():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = request.form.get("role") or "sales"
    if not name or not email or len(password) < 8:
        flash("Name, email, and a password of at least 8 characters are required.", "error")
        return redirect(url_for("admin.users"))
    if User.query.filter(User.email.ilike(email)).first():
        flash("That email is already registered.", "error")
        return redirect(url_for("admin.users"))
    if role not in ("admin", "manager", "sales"):
        role = "sales"
    user = User(name=name, email=email, role=role, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("User created.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/settings/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@roles_required("admin")
def user_toggle(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        user.is_active = not user.is_active
        db.session.commit()
        flash("User status updated.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/settings/api-keys")
@login_required
@roles_required("admin")
def api_keys():
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return render_template(
        "admin/api_keys.html",
        keys=keys,
        new_key=None,
        section="settings",
        subsection="api",
    )


@bp.route("/settings/api-keys/new", methods=["POST"])
@login_required
@roles_required("admin")
def api_key_new():
    name = (request.form.get("name") or "Customer App").strip()
    raw = "itg_" + secrets.token_urlsafe(32)
    key = ApiKey(
        name=name,
        prefix=raw[:12],
        key_hash=generate_password_hash(raw),
        created_by_id=current_user.id,
    )
    db.session.add(key)
    db.session.commit()
    flash("API key created. Copy it now — it will not be shown again.", "success")
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return render_template(
        "admin/api_keys.html",
        keys=keys,
        new_key=raw,
        section="settings",
        subsection="api",
    )


@bp.route("/settings/api-keys/<int:key_id>/toggle", methods=["POST"])
@login_required
@roles_required("admin")
def api_key_toggle(key_id):
    key = db.session.get(ApiKey, key_id)
    if key:
        key.is_active = not key.is_active
        db.session.commit()
        flash("API key updated.", "success")
    return redirect(url_for("admin.api_keys"))
