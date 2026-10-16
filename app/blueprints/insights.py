from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Activity, CustomerRequest, Deal, Lead, Organization, Person

bp = Blueprint("insights", __name__)


@bp.route("/insights")
@login_required
def dashboard():
    deal_by_stage = (
        db.session.query(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0))
        .filter(Deal.status == "open")
        .group_by(Deal.stage)
        .all()
    )
    pipeline = {stage: {"count": 0, "value": 0} for stage in Deal.STAGES}
    for stage, count, value in deal_by_stage:
        pipeline[stage] = {"count": count, "value": float(value or 0)}

    stats = {
        "people": Person.query.count(),
        "organizations": Organization.query.count(),
        "open_deals": Deal.query.filter_by(status="open").count(),
        "won_deals": Deal.query.filter_by(status="won").count(),
        "pipeline_value": float(
            db.session.query(func.coalesce(func.sum(Deal.value), 0))
            .filter(Deal.status == "open")
            .scalar()
            or 0
        ),
        "leads": Lead.query.filter(Lead.status != "converted").count(),
        "open_activities": Activity.query.filter_by(done=False).count(),
        "customer_requests": CustomerRequest.query.filter(
            CustomerRequest.status.in_(["new", "assigned"])
        ).count(),
    }
    recent_deals = Deal.query.order_by(Deal.created_at.desc()).limit(6).all()
    recent_requests = CustomerRequest.query.order_by(CustomerRequest.created_at.desc()).limit(6).all()
    return render_template(
        "insights/index.html",
        stats=stats,
        pipeline=pipeline,
        recent_deals=recent_deals,
        recent_requests=recent_requests,
        section="insights",
    )
