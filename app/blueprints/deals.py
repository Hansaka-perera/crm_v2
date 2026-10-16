from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.excel_io import workbook_from_rows
from app.extensions import db
from app.helpers import apply_search, apply_sort, owner_filter, paginate, selected_ids, users_for_select
from app.importers import import_deals
from app.import_views import handle_import, send_template
from app.models import Activity, Deal, Note, Organization, Person

bp = Blueprint("deals", __name__)


def _get_deal(deal_id):
    deal = db.session.get(Deal, deal_id)
    if not deal:
        abort(404)
    if not current_user.can_manage_all() and deal.owner_id != current_user.id:
        abort(403)
    return deal


@bp.route("/deals")
@login_required
def list_deals():
    q = request.args.get("q", "")
    stage = request.args.get("stage", "")
    status = request.args.get("status", "open")
    query = owner_filter(Deal.query, Deal)
    query = apply_search(query, Deal, ["title", "stage", "status"], q)
    if stage:
        query = query.filter(Deal.stage == stage)
    if status and status != "all":
        query = query.filter(Deal.status == status)
    query = apply_sort(query, Deal, "id", "desc")
    pagination = paginate(query)
    total_value = sum(d.value or 0 for d in pagination.items)
    return render_template(
        "deals/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        stage=stage,
        status=status,
        stages=Deal.STAGES,
        total_value=total_value,
        section="deals",
        users=users_for_select(),
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
    )


@bp.route("/deals/new", methods=["GET", "POST"])
@login_required
def deal_new():
    if request.method == "POST":
        deal = _save_deal(Deal(owner_id=current_user.id))
        if deal:
            flash("Deal created.", "success")
            return redirect(url_for("deals.deal_detail", deal_id=deal.id))
    return render_template(
        "deals/form.html",
        deal=None,
        stages=Deal.STAGES,
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        users=users_for_select(),
        section="deals",
    )


@bp.route("/deals/<int:deal_id>")
@login_required
def deal_detail(deal_id):
    deal = _get_deal(deal_id)
    return render_template(
        "deals/detail.html",
        deal=deal,
        stages=Deal.STAGES,
        activities=Activity.query.filter_by(deal_id=deal.id).order_by(Activity.due_at.desc()).all(),
        notes=Note.query.filter_by(deal_id=deal.id).order_by(Note.created_at.desc()).all(),
        section="deals",
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        users=users_for_select(),
    )


@bp.route("/deals/<int:deal_id>/edit", methods=["GET", "POST"])
@login_required
def deal_edit(deal_id):
    deal = _get_deal(deal_id)
    if request.method == "POST":
        if _save_deal(deal):
            flash("Deal updated.", "success")
            return redirect(url_for("deals.deal_detail", deal_id=deal.id))
    return render_template(
        "deals/form.html",
        deal=deal,
        stages=Deal.STAGES,
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        users=users_for_select(),
        section="deals",
    )


@bp.route("/deals/<int:deal_id>/stage", methods=["POST"])
@login_required
def deal_stage(deal_id):
    deal = _get_deal(deal_id)
    stage = request.form.get("stage")
    if stage in Deal.STAGES:
        deal.stage = stage
        if stage == "Contract Signed":
            deal.status = "won"
        db.session.commit()
        flash("Deal stage updated.", "success")
    return redirect(request.referrer or url_for("deals.list_deals"))


@bp.route("/deals/<int:deal_id>/status", methods=["POST"])
@login_required
def deal_status(deal_id):
    deal = _get_deal(deal_id)
    status = request.form.get("status")
    if status in ("open", "won", "lost"):
        deal.status = status
        db.session.commit()
        flash("Deal status updated.", "success")
    return redirect(url_for("deals.deal_detail", deal_id=deal.id))


@bp.route("/deals/<int:deal_id>/notes", methods=["POST"])
@login_required
def deal_note(deal_id):
    deal = _get_deal(deal_id)
    body = (request.form.get("body") or "").strip()
    if body:
        db.session.add(Note(body=body, deal_id=deal.id, user_id=current_user.id))
        db.session.commit()
        flash("Note added.", "success")
    return redirect(url_for("deals.deal_detail", deal_id=deal.id))


@bp.route("/deals/<int:deal_id>/delete", methods=["POST"])
@login_required
def deal_delete(deal_id):
    deal = _get_deal(deal_id)
    db.session.delete(deal)
    db.session.commit()
    flash("Deal deleted.", "success")
    return redirect(url_for("deals.list_deals"))


@bp.route("/deals/bulk-delete", methods=["POST"])
@login_required
def deals_bulk_delete():
    ids = selected_ids()
    count = owner_filter(Deal.query.filter(Deal.id.in_(ids)), Deal).delete(synchronize_session=False)
    db.session.commit()
    flash(f"Deleted {count} deals.", "success")
    return redirect(url_for("deals.list_deals"))


@bp.route("/deals/template")
@login_required
def deals_template():
    return send_template("deals", "itglow_deals_template.xlsx")


@bp.route("/deals/export")
@login_required
def deals_export():
    rows = []
    for d in owner_filter(Deal.query, Deal).order_by(Deal.id.desc()):
        rows.append(
            [
                d.title,
                d.value,
                d.currency,
                d.stage,
                d.status,
                d.organization.name if d.organization else "",
                d.person.name if d.person else "",
                d.owner.email if d.owner else "",
                d.expected_close_date.isoformat() if d.expected_close_date else "",
            ]
        )
    buf = workbook_from_rows(
        [
            "title",
            "value",
            "currency",
            "stage",
            "status",
            "organization",
            "contact_person",
            "owner_email",
            "expected_close_date",
        ],
        rows,
        "Deals",
    )
    return send_file(
        buf,
        as_attachment=True,
        download_name="itglow_deals.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/deals/import", methods=["GET", "POST"])
@login_required
def deals_import():
    return handle_import("deals", import_deals, "deals.list_deals", "deals.deals_template")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _save_deal(deal):
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Title is required.", "error")
        return None
    deal.title = title
    try:
        deal.value = float(request.form.get("value") or 0)
    except ValueError:
        flash("Value must be a number.", "error")
        return None
    deal.currency = request.form.get("currency") or "LKR"
    stage = request.form.get("stage") or "Qualified"
    deal.stage = stage if stage in Deal.STAGES else "Qualified"
    deal.status = request.form.get("status") or "open"
    deal.organization_id = request.form.get("organization_id") or None
    deal.person_id = request.form.get("person_id") or None
    deal.expected_close_date = _parse_date(request.form.get("expected_close_date"))
    deal.next_activity_date = _parse_date(request.form.get("next_activity_date"))
    owner_id = request.form.get("owner_id")
    if owner_id and current_user.can_manage_all():
        deal.owner_id = int(owner_id)
    db.session.add(deal)
    db.session.commit()
    return deal
