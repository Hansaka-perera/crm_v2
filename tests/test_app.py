import io
from pathlib import Path

from openpyxl import Workbook

from app import create_app
from app.extensions import db
from app.models import ApiKey, CustomerRequest, Deal, Person, User
from config import TestConfig


def make_client():
    app = create_app(TestConfig)
    return app, app.test_client()


def login(client, email="admin@itglow.local", password="Admin@123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_login_required():
    _app, client = make_client()
    response = client.get("/people")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_and_people_page():
    _app, client = make_client()
    response = login(client)
    assert response.status_code == 200
    assert b"Nina Patel" in response.data
    assert b"ITGlow CRM" in response.data


def test_create_person_persists():
    app, client = make_client()
    login(client)
    response = client.post(
        "/people/new",
        data={"name": "Amal Silva", "email": "amal@example.com", "phone": "011-1"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Person.query.filter_by(email="amal@example.com").first() is not None


def test_create_deal_table_view():
    app, client = make_client()
    login(client)
    response = client.post(
        "/deals/new",
        data={"title": "Website rebuild", "value": "15000", "stage": "Qualified", "status": "open"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    listing = client.get("/deals")
    assert b"Website rebuild" in listing.data
    assert b"Title" in listing.data
    with app.app_context():
        assert Deal.query.filter_by(title="Website rebuild").first() is not None


def test_all_nav_pages():
    _app, client = make_client()
    login(client)
    paths = [
        "/setup",
        "/people",
        "/organizations",
        "/contacts/timeline",
        "/contacts/merge",
        "/activities",
        "/deals",
        "/leads",
        "/leads/web-forms",
        "/leads/live-chat",
        "/leads/chatbot",
        "/leads/prospector",
        "/leads/web-visitors",
        "/insights",
        "/inbox",
        "/app-customers",
        "/settings/users",
        "/settings/api-keys",
        "/search?q=Nina",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path


def test_sales_cannot_open_admin():
    _app, client = make_client()
    login(client, "sales@itglow.local", "Sales@123")
    response = client.get("/settings/users")
    assert response.status_code == 403


def test_customer_api_requires_key():
    _app, client = make_client()
    response = client.post("/api/v1/customer-requests", json={"title": "x"})
    assert response.status_code == 401


def test_customer_api_creates_request():
    app, client = make_client()
    key_path = Path("instance/customer_api_key.txt")
    with app.app_context():
        assert ApiKey.query.count() == 1
    raw = key_path.read_text(encoding="utf-8").strip() if key_path.exists() else None
    if not raw:
        with app.app_context():
            # Seed writes the key relative to INSTANCE_DIR; read from db by generating a known key in test.
            from werkzeug.security import generate_password_hash
            from app.models import ApiKey as AK

            raw = "itg_testkey_value"
            db.session.add(
                AK(
                    name="test",
                    prefix=raw[:12],
                    key_hash=generate_password_hash(raw),
                    created_by_id=User.query.first().id,
                )
            )
            db.session.commit()
    response = client.post(
        "/api/v1/customer-requests",
        json={
            "customer_name": "Ravi Perera",
            "customer_email": "ravi@client.example",
            "title": "Need onboarding",
            "description": "Please set up our account",
        },
        headers={"X-API-Key": raw},
    )
    assert response.status_code == 201
    with app.app_context():
        assert CustomerRequest.query.filter_by(customer_email="ravi@client.example").first()


def test_excel_template_and_import_people():
    app, client = make_client()
    login(client)
    template = client.get("/people/template")
    assert template.status_code == 200
    assert template.mimetype.startswith("application/")

    wb = Workbook()
    ws = wb.active
    ws.append(["name", "email", "phone", "job_title", "organization", "owner_email"])
    ws.append(["Imported User", "imported@example.com", "555", "Buyer", "Bluecore Systems", ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    upload = client.post(
        "/people/import",
        data={"file": (buf, "people.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert b"Map columns" in upload.data
    commit = client.post(
        "/people/import",
        data={
            "step": "commit",
            "duplicate": "skip",
            "map_name": "name",
            "map_email": "email",
            "map_phone": "phone",
            "map_job_title": "job_title",
            "map_organization": "organization",
            "map_owner_email": "owner_email",
        },
        follow_redirects=True,
    )
    assert commit.status_code == 200
    with app.app_context():
        assert Person.query.filter_by(email="imported@example.com").first() is not None


def test_export_contains_seeded_people():
    _app, client = make_client()
    login(client)
    response = client.get("/people/export")
    assert response.status_code == 200
    assert b"Nina Patel" in response.data or b"nina.patel" in response.data


def test_bad_password():
    _app, client = make_client()
    response = login(client, password="wrong")
    assert b"Invalid email or password" in response.data
