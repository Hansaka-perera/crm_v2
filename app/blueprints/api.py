from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import ApiKey, CustomerRequest, utcnow

bp = Blueprint("api", __name__)


def _api_key():
    raw = request.headers.get(current_app.config["CUSTOMER_API_HEADER"], "")
    if not raw:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            raw = auth.split(" ", 1)[1].strip()
    return raw


def require_api_key():
    raw = _api_key()
    if not raw:
        return None
    prefix = raw[:12]
    keys = ApiKey.query.filter_by(prefix=prefix, is_active=True).all()
    for key in keys:
        if check_password_hash(key.key_hash, raw):
            key.last_used_at = utcnow()
            db.session.commit()
            return key
    return None


@bp.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ITGlow CRM"})


@bp.route("/customer-requests", methods=["POST"])
def create_customer_request():
    key = require_api_key()
    if not key:
        return jsonify({"error": "Invalid or missing API key."}), 401
    data = request.get_json(silent=True) or {}
    required = ["customer_name", "customer_email", "title"]
    missing = [f for f in required if not str(data.get(f) or "").strip()]
    if missing:
        return jsonify({"error": "Missing required fields.", "fields": missing}), 400
    email = data["customer_email"].strip()
    if "@" not in email:
        return jsonify({"error": "Invalid email address."}), 400
    item = CustomerRequest(
        external_id=(data.get("external_id") or "")[:80],
        customer_name=data["customer_name"].strip()[:200],
        customer_email=email[:255],
        customer_phone=(data.get("customer_phone") or "")[:64],
        organization_name=(data.get("organization_name") or "")[:200],
        request_type=(data.get("request_type") or "support")[:80],
        title=data["title"].strip()[:255],
        description=(data.get("description") or ""),
        status="new",
    )
    db.session.add(item)
    db.session.commit()
    return (
        jsonify(
            {
                "id": item.id,
                "status": item.status,
                "title": item.title,
                "created_at": item.created_at.isoformat(),
            }
        ),
        201,
    )


@bp.route("/customer-requests/<int:request_id>", methods=["GET"])
def get_customer_request(request_id):
    key = require_api_key()
    if not key:
        return jsonify({"error": "Invalid or missing API key."}), 401
    item = db.session.get(CustomerRequest, request_id)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify(
        {
            "id": item.id,
            "status": item.status,
            "title": item.title,
            "customer_name": item.customer_name,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
    )
