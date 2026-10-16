from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.excel_io import workbook_from_rows
from app.extensions import db
from app.helpers import apply_search, apply_sort, owner_filter, paginate, selected_ids, users_for_select
from app.importers import import_activities
from app.import_views import handle_import, send_template
from app.models import Activity, Deal, Organization, Person

bp = Blueprint("activities", __name__)


def _get(activity_id):
    activity = db.session.get(Activity, activity_id)
    if not activity:
        abort(404)
    if not current_user.can_manage_all() and activity.owner_id != current_user.id:
        abort(403)
    return activity


@bp.route("/activities")
@login_required
def list_activities():
    q = request.args.get("q", "")
    type_ = request.args.get("type", "")
    done = request.args.get("done", "")
    query = owner_filter(Activity.query, Activity)
    query = apply_search(query, Activity, ["subject", "type"], q)
    if type_:
        query = query.filter(Activity.type == type_)
    if done == "open":
        query = query.filter(Activity.done.is_(False))
    elif done == "done":
        query = query.filter(Activity.done.is_(True))
    query = apply_sort(query, Activity, "due_at", "asc")
    pagination = paginate(query)
    return render_template(
        "activities/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        type=type_,
        done=done,
        types=Activity.TYPES,
        section="activities",
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        deals=Deal.query.order_by(Deal.title).all(),
        users=users_for_select(),
    )


@bp.route("/activities/new", methods=["GET", "POST"])
@login_required
def activity_new():
    if request.method == "POST":
        activity = _save(Activity(owner_id=current_user.id))
        if activity:
            flash("Activity created.", "success")
            return redirect(url_for("activities.list_activities"))
    return render_template(
        "activities/form.html",
        activity=None,
        types=Activity.TYPES,
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        deals=Deal.query.order_by(Deal.title).all(),
        users=users_for_select(),
        section="activities",
    )


@bp.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def activity_edit(activity_id):
    activity = _get(activity_id)
    if request.method == "POST":
        if _save(activity):
            flash("Activity updated.", "success")
            return redirect(url_for("activities.list_activities"))
    return render_template(
        "activities/form.html",
        activity=activity,
        types=Activity.TYPES,
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        deals=Deal.query.order_by(Deal.title).all(),
        users=users_for_select(),
        section="activities",
    )


@bp.route("/activities/<int:activity_id>/toggle", methods=["POST"])
@login_required
def activity_toggle(activity_id):
    activity = _get(activity_id)
    activity.done = not activity.done
    db.session.commit()
    return redirect(request.referrer or url_for("activities.list_activities"))


@bp.route("/activities/<int:activity_id>/delete", methods=["POST"])
@login_required
def activity_delete(activity_id):
    activity = _get(activity_id)
    db.session.delete(activity)
    db.session.commit()
    flash("Activity deleted.", "success")
    return redirect(url_for("activities.list_activities"))


@bp.route("/activities/bulk-delete", methods=["POST"])
@login_required
def bulk_delete():
    ids = selected_ids()
    count = owner_filter(Activity.query.filter(Activity.id.in_(ids)), Activity).delete(
        synchronize_session=False
    )
    db.session.commit()
    flash(f"Deleted {count} activities.", "success")
    return redirect(url_for("activities.list_activities"))


@bp.route("/activities/template")
@login_required
def activities_template():
    return send_template("activities", "itglow_activities_template.xlsx")


@bp.route("/activities/export")
@login_required
def activities_export():
    rows = [
        [
            a.type,
            a.subject,
            a.due_at.isoformat(sep=" ") if a.due_at else "",
            "yes" if a.done else "no",
            a.person.name if a.person else "",
            a.organization.name if a.organization else "",
            a.deal.title if a.deal else "",
            a.owner.email if a.owner else "",
        ]
        for a in owner_filter(Activity.query, Activity)
    ]
    buf = workbook_from_rows(
        ["type", "subject", "due_at", "done", "person", "organization", "deal", "owner_email"],
        rows,
        "Activities",
    )
    return send_file(
        buf,
        as_attachment=True,
        download_name="itglow_activities.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/activities/import", methods=["GET", "POST"])
@login_required
def activities_import():
    return handle_import(
        "activities",
        import_activities,
        "activities.list_activities",
        "activities.activities_template",
    )


def _save(activity):
    subject = (request.form.get("subject") or "").strip()
    if not subject:
        flash("Subject is required.", "error")
        return None
    activity.subject = subject
    activity.type = request.form.get("type") or "task"
    due = request.form.get("due_at")
    activity.due_at = datetime.fromisoformat(due) if due else None
    activity.notes = request.form.get("notes") or ""
    activity.done = request.form.get("done") == "on"
    activity.person_id = request.form.get("person_id") or None
    activity.organization_id = request.form.get("organization_id") or None
    activity.deal_id = request.form.get("deal_id") or None
    db.session.add(activity)
    db.session.commit()
    return activity
