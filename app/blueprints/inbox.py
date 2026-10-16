from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.helpers import apply_search, owner_filter, paginate
from app.models import InboxMessage, Person

bp = Blueprint("inbox", __name__)


@bp.route("/inbox")
@login_required
def list_messages():
    q = request.args.get("q", "")
    query = owner_filter(InboxMessage.query, InboxMessage)
    query = apply_search(query, InboxMessage, ["subject", "from_email", "body"], q)
    unread = request.args.get("unread")
    if unread == "1":
        query = query.filter(InboxMessage.is_read.is_(False))
    pagination = paginate(query.order_by(InboxMessage.created_at.desc()))
    return render_template(
        "inbox/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        unread=unread,
        people=Person.query.order_by(Person.name).all(),
        section="inbox",
    )


@bp.route("/inbox/new", methods=["POST"])
@login_required
def message_new():
    subject = (request.form.get("subject") or "").strip()
    if not subject:
        flash("Subject is required.", "error")
        return redirect(url_for("inbox.list_messages"))
    db.session.add(
        InboxMessage(
            subject=subject,
            body=request.form.get("body") or "",
            from_email=request.form.get("from_email") or current_user.email,
            person_id=request.form.get("person_id") or None,
            owner_id=current_user.id,
        )
    )
    db.session.commit()
    flash("Message saved to Sales Inbox.", "success")
    return redirect(url_for("inbox.list_messages"))


@bp.route("/inbox/<int:message_id>")
@login_required
def message_detail(message_id):
    message = db.session.get(InboxMessage, message_id)
    if not message:
        abort(404)
    if not current_user.can_manage_all() and message.owner_id != current_user.id:
        abort(403)
    if not message.is_read:
        message.is_read = True
        db.session.commit()
    return render_template("inbox/detail.html", message=message, section="inbox")


@bp.route("/inbox/<int:message_id>/delete", methods=["POST"])
@login_required
def message_delete(message_id):
    message = db.session.get(InboxMessage, message_id)
    if not message:
        abort(404)
    db.session.delete(message)
    db.session.commit()
    flash("Message deleted.", "success")
    return redirect(url_for("inbox.list_messages"))
