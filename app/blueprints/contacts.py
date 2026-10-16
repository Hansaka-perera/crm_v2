from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.excel_io import workbook_from_rows
from app.extensions import db
from app.helpers import apply_search, apply_sort, owner_filter, paginate, selected_ids, users_for_select
from app.importers import import_organizations, import_people
from app.import_views import handle_import, send_template
from app.models import Activity, Deal, Note, Organization, Person

bp = Blueprint("contacts", __name__)


@bp.route("/people")
@login_required
def people():
    q = request.args.get("q", "")
    query = owner_filter(Person.query, Person)
    query = apply_search(query, Person, ["name", "email", "phone"], q)
    query = apply_sort(query, Person, "name", "asc")
    pagination = paginate(query)
    return render_template(
        "people/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        section="contacts",
        subsection="people",
        users=users_for_select(),
        organizations=Organization.query.order_by(Organization.name).all(),
    )


@bp.route("/people/new", methods=["GET", "POST"])
@login_required
def person_new():
    if request.method == "POST":
        person = _save_person(Person(owner_id=current_user.id))
        if person:
            flash("Person created.", "success")
            return redirect(url_for("contacts.person_detail", person_id=person.id))
    return render_template(
        "people/form.html",
        person=None,
        organizations=Organization.query.order_by(Organization.name).all(),
        users=users_for_select(),
        section="contacts",
        subsection="people",
    )


@bp.route("/people/<int:person_id>")
@login_required
def person_detail(person_id):
    person = _get_person(person_id)
    return render_template(
        "people/detail.html",
        person=person,
        activities=Activity.query.filter_by(person_id=person.id).order_by(Activity.due_at.desc()).all(),
        deals=Deal.query.filter_by(person_id=person.id).all(),
        notes=Note.query.filter_by(person_id=person.id).order_by(Note.created_at.desc()).all(),
        section="contacts",
        subsection="people",
        users=users_for_select(),
        organizations=Organization.query.order_by(Organization.name).all(),
    )


@bp.route("/people/<int:person_id>/edit", methods=["GET", "POST"])
@login_required
def person_edit(person_id):
    person = _get_person(person_id)
    if request.method == "POST":
        if _save_person(person):
            flash("Person updated.", "success")
            return redirect(url_for("contacts.person_detail", person_id=person.id))
    return render_template(
        "people/form.html",
        person=person,
        organizations=Organization.query.order_by(Organization.name).all(),
        users=users_for_select(),
        section="contacts",
        subsection="people",
    )


@bp.route("/people/<int:person_id>/delete", methods=["POST"])
@login_required
def person_delete(person_id):
    person = _get_person(person_id)
    db.session.delete(person)
    db.session.commit()
    flash("Person deleted.", "success")
    return redirect(url_for("contacts.people"))


@bp.route("/people/<int:person_id>/notes", methods=["POST"])
@login_required
def person_note(person_id):
    person = _get_person(person_id)
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Note cannot be empty.", "error")
    else:
        db.session.add(Note(body=body, person_id=person.id, user_id=current_user.id))
        db.session.commit()
        flash("Note added.", "success")
    return redirect(url_for("contacts.person_detail", person_id=person.id))


@bp.route("/people/bulk-delete", methods=["POST"])
@login_required
def people_bulk_delete():
    ids = selected_ids()
    query = owner_filter(Person.query.filter(Person.id.in_(ids)), Person)
    count = query.delete(synchronize_session=False)
    db.session.commit()
    flash(f"Deleted {count} people.", "success")
    return redirect(url_for("contacts.people"))


@bp.route("/people/template")
@login_required
def people_template():
    return send_template("people", "itglow_people_template.xlsx")


@bp.route("/people/export")
@login_required
def people_export():
    rows = []
    for p in owner_filter(Person.query, Person).order_by(Person.name).all():
        rows.append(
            [
                p.name,
                p.email,
                p.phone,
                p.job_title,
                p.organization.name if p.organization else "",
                p.owner.email if p.owner else "",
            ]
        )
    buf = workbook_from_rows(
        ["name", "email", "phone", "job_title", "organization", "owner_email"],
        rows,
        "People",
    )
    return send_file(
        buf,
        as_attachment=True,
        download_name="itglow_people.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/people/import", methods=["GET", "POST"])
@login_required
def people_import():
    return handle_import("people", import_people, "contacts.people", "contacts.people_template")


@bp.route("/organizations")
@login_required
def organizations():
    q = request.args.get("q", "")
    query = owner_filter(Organization.query, Organization)
    query = apply_search(query, Organization, ["name", "address", "phone"], q)
    query = apply_sort(query, Organization, "name", "asc")
    pagination = paginate(query)
    people_counts = dict(
        db.session.query(Person.organization_id, func.count(Person.id))
        .group_by(Person.organization_id)
        .all()
    )
    closed_counts = dict(
        db.session.query(Deal.organization_id, func.count(Deal.id))
        .filter(Deal.status.in_(["won", "lost"]))
        .group_by(Deal.organization_id)
        .all()
    )
    return render_template(
        "organizations/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        people_counts=people_counts,
        closed_counts=closed_counts,
        section="contacts",
        subsection="organizations",
        users=users_for_select(),
    )


@bp.route("/organizations/new", methods=["GET", "POST"])
@login_required
def organization_new():
    if request.method == "POST":
        org = _save_org(Organization(owner_id=current_user.id))
        if org:
            flash("Organization created.", "success")
            return redirect(url_for("contacts.organization_detail", org_id=org.id))
    return render_template(
        "organizations/form.html",
        org=None,
        users=users_for_select(),
        section="contacts",
        subsection="organizations",
    )


@bp.route("/organizations/<int:org_id>")
@login_required
def organization_detail(org_id):
    org = _get_org(org_id)
    return render_template(
        "organizations/detail.html",
        org=org,
        people=Person.query.filter_by(organization_id=org.id).all(),
        deals=Deal.query.filter_by(organization_id=org.id).all(),
        activities=Activity.query.filter_by(organization_id=org.id).order_by(Activity.due_at.desc()).all(),
        section="contacts",
        subsection="organizations",
        users=users_for_select(),
    )


@bp.route("/organizations/<int:org_id>/edit", methods=["GET", "POST"])
@login_required
def organization_edit(org_id):
    org = _get_org(org_id)
    if request.method == "POST":
        if _save_org(org):
            flash("Organization updated.", "success")
            return redirect(url_for("contacts.organization_detail", org_id=org.id))
    return render_template(
        "organizations/form.html",
        org=org,
        users=users_for_select(),
        section="contacts",
        subsection="organizations",
    )


@bp.route("/organizations/<int:org_id>/delete", methods=["POST"])
@login_required
def organization_delete(org_id):
    org = _get_org(org_id)
    db.session.delete(org)
    db.session.commit()
    flash("Organization deleted.", "success")
    return redirect(url_for("contacts.organizations"))


@bp.route("/organizations/bulk-delete", methods=["POST"])
@login_required
def organizations_bulk_delete():
    ids = selected_ids()
    query = owner_filter(Organization.query.filter(Organization.id.in_(ids)), Organization)
    count = query.delete(synchronize_session=False)
    db.session.commit()
    flash(f"Deleted {count} organizations.", "success")
    return redirect(url_for("contacts.organizations"))


@bp.route("/organizations/template")
@login_required
def organizations_template():
    return send_template("organizations", "itglow_organizations_template.xlsx")


@bp.route("/organizations/export")
@login_required
def organizations_export():
    rows = [
        [o.name, o.address, o.website, o.phone, o.owner.email if o.owner else ""]
        for o in owner_filter(Organization.query, Organization).order_by(Organization.name)
    ]
    buf = workbook_from_rows(["name", "address", "website", "phone", "owner_email"], rows, "Organizations")
    return send_file(
        buf,
        as_attachment=True,
        download_name="itglow_organizations.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/organizations/import", methods=["GET", "POST"])
@login_required
def organizations_import():
    return handle_import(
        "organizations",
        import_organizations,
        "contacts.organizations",
        "contacts.organizations_template",
    )


@bp.route("/contacts/timeline")
@login_required
def timeline():
    people = owner_filter(Person.query, Person).order_by(Person.name).all()
    months_back = int(request.args.get("months", 3))
    return render_template(
        "timeline/index.html",
        people=people,
        months_back=months_back,
        section="contacts",
        subsection="timeline",
    )


@bp.route("/contacts/merge", methods=["GET", "POST"])
@login_required
def merge():
    groups = []
    dupes = (
        db.session.query(Person.email, func.count(Person.id))
        .filter(Person.email != "")
        .group_by(Person.email)
        .having(func.count(Person.id) > 1)
        .all()
    )
    for email, _count in dupes:
        groups.append(Person.query.filter_by(email=email).order_by(Person.id).all())

    if request.method == "POST":
        keep_id = request.form.get("keep", type=int)
        merge_ids = [int(i) for i in request.form.getlist("merge_ids") if i.isdigit()]
        keep = db.session.get(Person, keep_id)
        if not keep:
            flash("Select a contact to keep.", "error")
            return redirect(url_for("contacts.merge"))
        for pid in merge_ids:
            if pid == keep.id:
                continue
            other = db.session.get(Person, pid)
            if not other:
                continue
            Activity.query.filter_by(person_id=other.id).update({"person_id": keep.id})
            Deal.query.filter_by(person_id=other.id).update({"person_id": keep.id})
            Note.query.filter_by(person_id=other.id).update({"person_id": keep.id})
            db.session.delete(other)
        db.session.commit()
        flash("Duplicates merged.", "success")
        return redirect(url_for("contacts.merge"))

    return render_template(
        "merge/index.html",
        groups=groups,
        section="contacts",
        subsection="merge",
    )


def _save_person(person):
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Name is required.", "error")
        return None
    person.name = name
    person.email = (request.form.get("email") or "").strip()
    person.phone = (request.form.get("phone") or "").strip()
    person.job_title = (request.form.get("job_title") or "").strip()
    org_id = request.form.get("organization_id")
    person.organization_id = int(org_id) if org_id else None
    owner_id = request.form.get("owner_id")
    if owner_id and current_user.can_manage_all():
        person.owner_id = int(owner_id)
    db.session.add(person)
    db.session.commit()
    return person


def _save_org(org):
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Name is required.", "error")
        return None
    org.name = name
    org.address = (request.form.get("address") or "").strip()
    org.website = (request.form.get("website") or "").strip()
    org.phone = (request.form.get("phone") or "").strip()
    owner_id = request.form.get("owner_id")
    if owner_id and current_user.can_manage_all():
        org.owner_id = int(owner_id)
    db.session.add(org)
    db.session.commit()
    return org


def _get_person(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    if not current_user.can_manage_all() and person.owner_id != current_user.id:
        abort(403)
    return person


def _get_org(org_id):
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    if not current_user.can_manage_all() and org.owner_id != current_user.id:
        abort(403)
    return org
