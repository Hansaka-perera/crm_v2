from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.excel_io import workbook_from_rows
from app.extensions import db
from app.helpers import apply_search, apply_sort, paginate, roles_required, selected_ids, users_for_select
from app.importers import import_customers
from app.import_views import handle_import, send_template
from app.models import CustomerRequest, Organization, Person, utcnow

bp = Blueprint("customers", __name__)


def _get(request_id):
    item = db.session.get(CustomerRequest, request_id)
    if not item:
        abort(404)
    if current_user.role == "sales" and item.assigned_to_id not in (None, current_user.id):
        abort(403)
    return item


@bp.route("/app-customers")
@login_required
def list_requests():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    query = CustomerRequest.query
    if current_user.role == "sales":
        query = query.filter(
            (CustomerRequest.assigned_to_id == current_user.id)
            | (CustomerRequest.assigned_to_id.is_(None))
        )
    query = apply_search(
        query, CustomerRequest, ["title", "customer_name", "customer_email", "organization_name"], q
    )
    if status:
        query = query.filter(CustomerRequest.status == status)
    query = apply_sort(query, CustomerRequest, "id", "desc")
    pagination = paginate(query)
    return render_template(
        "customers/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        status=status,
        statuses=CustomerRequest.STATUSES,
        users=users_for_select(),
        section="customers",
    )


@bp.route("/app-customers/<int:request_id>")
@login_required
def detail(request_id):
    item = _get(request_id)
    return render_template(
        "customers/detail.html",
        item=item,
        statuses=CustomerRequest.STATUSES,
        users=users_for_select(),
        people=Person.query.order_by(Person.name).all(),
        organizations=Organization.query.order_by(Organization.name).all(),
        section="customers",
    )


@bp.route("/app-customers/<int:request_id>/update", methods=["POST"])
@login_required
def update(request_id):
    item = _get(request_id)
    action = request.form.get("action")
    if action == "assign":
        item.assigned_to_id = request.form.get("assigned_to_id") or None
        item.status = "assigned" if item.assigned_to_id else item.status
    elif action == "approve":
        if current_user.role not in ("admin", "manager"):
            abort(403)
        item.status = "approved"
    elif action == "reject":
        if current_user.role not in ("admin", "manager"):
            abort(403)
        item.status = "rejected"
    elif action == "complete":
        item.status = "completed"
    elif action == "link":
        item.person_id = request.form.get("person_id") or None
        item.organization_id = request.form.get("organization_id") or None
    notes = (request.form.get("notes") or "").strip()
    if notes:
        item.notes = ((item.notes or "") + f"\n[{current_user.name}] {notes}").strip()
    item.updated_at = utcnow()
    db.session.commit()
    flash("Customer request updated.", "success")
    return redirect(url_for("customers.detail", request_id=item.id))


@bp.route("/app-customers/<int:request_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "manager")
def delete(request_id):
    item = _get(request_id)
    db.session.delete(item)
    db.session.commit()
    flash("Customer request deleted.", "success")
    return redirect(url_for("customers.list_requests"))


@bp.route("/app-customers/bulk-delete", methods=["POST"])
@login_required
@roles_required("admin", "manager")
def bulk_delete():
    ids = selected_ids()
    count = CustomerRequest.query.filter(CustomerRequest.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    flash(f"Deleted {count} customer requests.", "success")
    return redirect(url_for("customers.list_requests"))


@bp.route("/app-customers/template")
@login_required
def template():
    return send_template("customers", "itglow_customers_template.xlsx")


@bp.route("/app-customers/export")
@login_required
def export():
    rows = [
        [
            c.customer_name,
            c.customer_email,
            c.customer_phone,
            c.organization_name,
            c.request_type,
            c.title,
            c.description,
            c.status,
        ]
        for c in CustomerRequest.query.order_by(CustomerRequest.id.desc())
    ]
    buf = workbook_from_rows(
        [
            "customer_name",
            "customer_email",
            "customer_phone",
            "organization_name",
            "request_type",
            "title",
            "description",
            "status",
        ],
        rows,
        "Customers",
    )
    return send_file(
        buf,
        as_attachment=True,
        download_name="itglow_customers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/app-customers/import", methods=["GET", "POST"])
@login_required
@roles_required("admin", "manager")
def import_file():
    return handle_import(
        "customers", import_customers, "customers.list_requests", "customers.template"
    )
