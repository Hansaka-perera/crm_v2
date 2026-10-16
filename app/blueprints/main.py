from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from sqlalchemy import or_

from app.helpers import owner_filter
from app.models import Activity, CustomerRequest, Deal, Lead, Organization, Person

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("redirect_home.html")


@bp.route("/setup")
@login_required
def setup_guide():
    counts = {
        "people": Person.query.count(),
        "organizations": Organization.query.count(),
        "deals": Deal.query.count(),
        "leads": Lead.query.count(),
        "activities": Activity.query.count(),
        "customers": CustomerRequest.query.count(),
    }
    return render_template("setup.html", counts=counts, section="setup")


@bp.route("/search")
@login_required
def search():
    q = (request.args.get("q") or "").strip()
    people = orgs = deals = leads = customers = []
    if q:
        like = f"%{q}%"
        people = owner_filter(Person.query, Person).filter(
            or_(Person.name.ilike(like), Person.email.ilike(like))
        ).limit(8).all()
        orgs = owner_filter(Organization.query, Organization).filter(
            Organization.name.ilike(like)
        ).limit(8).all()
        deals = owner_filter(Deal.query, Deal).filter(Deal.title.ilike(like)).limit(8).all()
        leads = owner_filter(Lead.query, Lead).filter(
            or_(Lead.title.ilike(like), Lead.email.ilike(like))
        ).limit(8).all()
        customers = CustomerRequest.query.filter(
            or_(
                CustomerRequest.title.ilike(like),
                CustomerRequest.customer_name.ilike(like),
                CustomerRequest.customer_email.ilike(like),
            )
        ).limit(8).all()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(
            {
                "people": [{"id": p.id, "name": p.name} for p in people],
                "organizations": [{"id": o.id, "name": o.name} for o in orgs],
                "deals": [{"id": d.id, "title": d.title} for d in deals],
                "leads": [{"id": l.id, "title": l.title} for l in leads],
                "customers": [{"id": c.id, "title": c.title} for c in customers],
            }
        )
    return render_template(
        "search.html",
        q=q,
        people=people,
        organizations=orgs,
        deals=deals,
        leads=leads,
        customers=customers,
        section="search",
    )
