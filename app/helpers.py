from functools import wraps

from flask import abort, request
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import User


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def owner_filter(query, model):
    if current_user.can_manage_all():
        return query
    if hasattr(model, "owner_id"):
        return query.filter(model.owner_id == current_user.id)
    if hasattr(model, "assigned_to_id"):
        return query.filter(
            or_(model.assigned_to_id == current_user.id, model.assigned_to_id.is_(None))
        )
    return query


def paginate(query, per_page=None):
    page = request.args.get("page", 1, type=int)
    per_page = per_page or 25
    return query.paginate(page=page, per_page=per_page, error_out=False)


def apply_search(query, model, columns, q):
    if not q:
        return query
    like = f"%{q.strip()}%"
    return query.filter(or_(*[getattr(model, col).ilike(like) for col in columns]))


def apply_sort(query, model, default="id", default_dir="desc"):
    sort = request.args.get("sort", default)
    direction = request.args.get("dir", default_dir)
    column = getattr(model, sort, getattr(model, default))
    return query.order_by(column.asc() if direction == "asc" else column.desc())


def selected_ids():
    ids = request.form.getlist("selected")
    return [int(i) for i in ids if str(i).isdigit()]


def users_for_select():
    return User.query.filter_by(is_active=True).order_by(User.name).all()


def commit():
    db.session.commit()
