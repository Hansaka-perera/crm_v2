from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf

from app.excel_io import workbook_from_rows
from app.extensions import db
from app.helpers import apply_search, apply_sort, owner_filter, paginate, selected_ids, users_for_select
from app.importers import import_leads
from app.import_views import handle_import, send_template
from app.models import Deal, Lead, Organization, Person, WebForm

bp = Blueprint("leads", __name__)


def _get_lead(lead_id):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        abort(404)
    if not current_user.can_manage_all() and lead.owner_id != current_user.id:
        abort(403)
    return lead


@bp.route("/leads")
@login_required
def inbox():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    query = owner_filter(Lead.query, Lead)
    query = apply_search(query, Lead, ["title", "person_name", "email", "organization_name"], q)
    if status:
        query = query.filter(Lead.status == status)
    query = apply_sort(query, Lead, "id", "desc")
    pagination = paginate(query)
    return render_template(
        "leads/list.html",
        pagination=pagination,
        items=pagination.items,
        q=q,
        status=status,
        statuses=Lead.STATUSES,
        section="leads",
        subsection="inbox",
        users=users_for_select(),
    )


@bp.route("/leads/new", methods=["GET", "POST"])
@login_required
def lead_new():
    if request.method == "POST":
        lead = _save_lead(Lead(owner_id=current_user.id, source="manual"))
        if lead:
            flash("Lead created.", "success")
            return redirect(url_for("leads.lead_detail", lead_id=lead.id))
    return render_template(
        "leads/form.html",
        lead=None,
        statuses=Lead.STATUSES,
        users=users_for_select(),
        section="leads",
        subsection="inbox",
    )


@bp.route("/leads/<int:lead_id>")
@login_required
def lead_detail(lead_id):
    lead = _get_lead(lead_id)
    return render_template(
        "leads/detail.html",
        lead=lead,
        statuses=Lead.STATUSES,
        users=users_for_select(),
        section="leads",
        subsection="inbox",
    )


@bp.route("/leads/<int:lead_id>/edit", methods=["GET", "POST"])
@login_required
def lead_edit(lead_id):
    lead = _get_lead(lead_id)
    if request.method == "POST":
        if _save_lead(lead):
            flash("Lead updated.", "success")
            return redirect(url_for("leads.lead_detail", lead_id=lead.id))
    return render_template(
        "leads/form.html",
        lead=lead,
        statuses=Lead.STATUSES,
        users=users_for_select(),
        section="leads",
        subsection="inbox",
    )


@bp.route("/leads/<int:lead_id>/convert", methods=["POST"])
@login_required
def lead_convert(lead_id):
    lead = _get_lead(lead_id)
    org = None
    if lead.organization_name:
        org = Organization.query.filter(Organization.name.ilike(lead.organization_name)).first()
        if not org:
            org = Organization(name=lead.organization_name, owner_id=current_user.id)
            db.session.add(org)
            db.session.flush()
    person = None
    if lead.person_name or lead.email:
        if lead.email:
            person = Person.query.filter(Person.email.ilike(lead.email)).first()
        if not person:
            person = Person(
                name=lead.person_name or lead.title,
                email=lead.email,
                phone=lead.phone,
                organization_id=org.id if org else None,
                owner_id=current_user.id,
            )
            db.session.add(person)
            db.session.flush()
    deal = Deal(
        title=lead.title,
        organization_id=org.id if org else None,
        person_id=person.id if person else None,
        owner_id=current_user.id,
        stage="Qualified",
        status="open",
    )
    db.session.add(deal)
    lead.status = "converted"
    lead.person_id = person.id if person else None
    lead.organization_id = org.id if org else None
    db.session.commit()
    flash("Lead converted into a person, organization, and deal.", "success")
    return redirect(url_for("deals.deal_detail", deal_id=deal.id))


@bp.route("/leads/<int:lead_id>/delete", methods=["POST"])
@login_required
def lead_delete(lead_id):
    lead = _get_lead(lead_id)
    db.session.delete(lead)
    db.session.commit()
    flash("Lead deleted.", "success")
    return redirect(url_for("leads.inbox"))


@bp.route("/leads/bulk-delete", methods=["POST"])
@login_required
def leads_bulk_delete():
    ids = selected_ids()
    count = owner_filter(Lead.query.filter(Lead.id.in_(ids)), Lead).delete(synchronize_session=False)
    db.session.commit()
    flash(f"Deleted {count} leads.", "success")
    return redirect(url_for("leads.inbox"))


@bp.route("/leads/template")
@login_required
def leads_template():
    return send_template("leads", "itglow_leads_template.xlsx")


@bp.route("/leads/export")
@login_required
def leads_export():
    rows = [
        [
            l.title,
            l.person_name,
            l.email,
            l.phone,
            l.organization_name,
            l.source,
            l.status,
            l.owner.email if l.owner else "",
        ]
        for l in owner_filter(Lead.query, Lead)
    ]
    buf = workbook_from_rows(
        ["title", "person_name", "email", "phone", "organization_name", "source", "status", "owner_email"],
        rows,
        "Leads",
    )
    return send_file(
        buf,
        as_attachment=True,
        download_name="itglow_leads.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/leads/import", methods=["GET", "POST"])
@login_required
def leads_import():
    return handle_import("leads", import_leads, "leads.inbox", "leads.leads_template")


@bp.route("/leads/web-forms")
@login_required
def web_forms():
    forms = WebForm.query.order_by(WebForm.name).all()
    return render_template(
        "leads/web_forms.html",
        forms=forms,
        section="leads",
        subsection="web_forms",
    )


@bp.route("/leads/web-forms/new", methods=["POST"])
@login_required
def web_form_new():
    name = (request.form.get("name") or "").strip()
    slug = (request.form.get("slug") or "").strip().lower().replace(" ", "-")
    if not name or not slug:
        flash("Name and slug are required.", "error")
    elif WebForm.query.filter_by(slug=slug).first():
        flash("That slug is already in use.", "error")
    else:
        db.session.add(WebForm(name=name, slug=slug, is_active=True))
        db.session.commit()
        flash("Web form created.", "success")
    return redirect(url_for("leads.web_forms"))


@bp.route("/forms/<slug>", methods=["GET", "POST"])
def public_form(slug):
    form = WebForm.query.filter_by(slug=slug, is_active=True).first_or_404()
    if request.method == "POST":
        title = (request.form.get("title") or request.form.get("message") or "Website lead").strip()
        person_name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        if not person_name or not email:
            flash("Name and email are required.", "error")
        else:
            db.session.add(
                Lead(
                    title=title[:255],
                    person_name=person_name,
                    email=email,
                    phone=(request.form.get("phone") or "").strip(),
                    organization_name=(request.form.get("organization") or "").strip(),
                    source=f"web_form:{form.slug}",
                    status="new",
                )
            )
            db.session.commit()
            flash("Thanks — your request was received.", "success")
            return redirect(url_for("leads.public_form", slug=slug))
    return render_template("leads/public_form.html", form=form, csrf_token=generate_csrf())


@bp.route("/leads/live-chat")
@login_required
def live_chat():
    return render_template("leads/tool.html", tool="live_chat", section="leads", subsection="live_chat")


@bp.route("/leads/chatbot")
@login_required
def chatbot():
    return render_template("leads/tool.html", tool="chatbot", section="leads", subsection="chatbot")


@bp.route("/leads/prospector")
@login_required
def prospector():
    q = request.args.get("q", "")
    orgs = Organization.query.order_by(Organization.name)
    if q:
        orgs = orgs.filter(Organization.name.ilike(f"%{q}%"))
    return render_template(
        "leads/prospector.html",
        organizations=orgs.limit(50).all(),
        q=q,
        section="leads",
        subsection="prospector",
    )


@bp.route("/leads/web-visitors")
@login_required
def web_visitors():
    recent = Lead.query.filter(Lead.source.like("web_form%")).order_by(Lead.created_at.desc()).limit(50).all()
    return render_template(
        "leads/web_visitors.html",
        items=recent,
        section="leads",
        subsection="web_visitors",
    )


def _save_lead(lead):
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Title is required.", "error")
        return None
    lead.title = title
    lead.person_name = (request.form.get("person_name") or "").strip()
    lead.email = (request.form.get("email") or "").strip()
    lead.phone = (request.form.get("phone") or "").strip()
    lead.organization_name = (request.form.get("organization_name") or "").strip()
    lead.status = request.form.get("status") or "new"
    owner_id = request.form.get("owner_id")
    if owner_id and current_user.can_manage_all():
        lead.owner_id = int(owner_id)
    db.session.add(lead)
    db.session.commit()
    return lead
