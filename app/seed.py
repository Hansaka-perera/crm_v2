import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Activity,
    ApiKey,
    Deal,
    InboxMessage,
    Lead,
    Organization,
    Person,
    User,
    WebForm,
)
from config import INSTANCE_DIR


def ensure_defaults():
    if User.query.count() == 0:
        admin = User(name="Hansaka Perera", email="admin@itglow.local", role="admin")
        admin.set_password("Admin@123")
        manager = User(name="ITGlow Manager", email="manager@itglow.local", role="manager")
        manager.set_password("Manager@123")
        sales = User(name="Sales User", email="sales@itglow.local", role="sales")
        sales.set_password("Sales@123")
        db.session.add_all([admin, manager, sales])
        db.session.flush()

        bluecore = Organization(
            name="Bluecore Systems",
            address="Colombo, Sri Lanka",
            website="https://bluecoresystems.com",
            phone="011-555-0100",
            owner_id=admin.id,
        )
        axiom = Organization(
            name="Axiom Telecom",
            address="Kandy, Sri Lanka",
            website="https://axiomtelecom.com",
            phone="081-555-0200",
            owner_id=admin.id,
        )
        db.session.add_all([bluecore, axiom])
        db.session.flush()

        nina = Person(
            name="Nina Patel",
            email="nina.patel@bluecoresystems.com",
            phone="512-555-0142",
            job_title="IT Director",
            organization_id=bluecore.id,
            owner_id=admin.id,
        )
        mark = Person(
            name="Mark Evans",
            email="mark.evans@axiomtelecom.com",
            phone="737-555-0763",
            job_title="Operations Lead",
            organization_id=axiom.id,
            owner_id=admin.id,
        )
        db.session.add_all([nina, mark])
        db.session.flush()

        deal1 = Deal(
            title="Cloud Migration Project",
            value=98000,
            currency="LKR",
            stage="Demo Completed",
            organization_id=axiom.id,
            person_id=mark.id,
            owner_id=admin.id,
            expected_close_date=date(2026, 11, 2),
            next_activity_date=date(2026, 10, 14),
        )
        deal2 = Deal(
            title="Managed IT Support Contract",
            value=31200,
            currency="LKR",
            stage="Negotiations",
            organization_id=bluecore.id,
            person_id=nina.id,
            owner_id=admin.id,
            expected_close_date=date(2026, 10, 26),
            next_activity_date=date(2026, 10, 13),
        )
        db.session.add_all([deal1, deal2])
        db.session.flush()

        now = datetime.now(timezone.utc)
        for person, org, deal in ((mark, axiom, deal1), (nina, bluecore, deal2)):
            db.session.add_all(
                [
                    Activity(
                        type="call",
                        subject=f"Discovery call with {person.name}",
                        due_at=now - timedelta(days=20),
                        done=True,
                        person_id=person.id,
                        organization_id=org.id,
                        deal_id=deal.id,
                        owner_id=admin.id,
                    ),
                    Activity(
                        type="meeting",
                        subject=f"Demo for {org.name}",
                        due_at=now - timedelta(days=5),
                        done=True,
                        person_id=person.id,
                        organization_id=org.id,
                        deal_id=deal.id,
                        owner_id=admin.id,
                    ),
                    Activity(
                        type="task",
                        subject="Send proposal follow-up",
                        due_at=now + timedelta(days=1),
                        done=False,
                        person_id=person.id,
                        organization_id=org.id,
                        deal_id=deal.id,
                        owner_id=admin.id,
                    ),
                ]
            )

        db.session.add(
            Lead(
                title="Website inquiry — network upgrade",
                person_name="Samira Fernando",
                email="samira@example.com",
                phone="077-555-0199",
                organization_name="Lanka Logistics",
                source="web_form",
                status="new",
                owner_id=sales.id,
            )
        )
        db.session.add(
            InboxMessage(
                subject="Proposal questions for Managed IT Support",
                body="Hi, can we review the SLA terms before signing?",
                from_email="nina.patel@bluecoresystems.com",
                person_id=nina.id,
                owner_id=admin.id,
            )
        )
        db.session.add(
            WebForm(name="Website contact", slug="website-contact", is_active=True)
        )

    if ApiKey.query.count() == 0:
        raw = "itg_" + secrets.token_urlsafe(32)
        prefix = raw[:12]
        key = ApiKey(
            name="Customer App",
            prefix=prefix,
            key_hash=generate_password_hash(raw),
            created_by_id=User.query.filter_by(role="admin").first().id,
        )
        db.session.add(key)
        key_path = Path(INSTANCE_DIR) / "customer_api_key.txt"
        key_path.write_text(raw, encoding="utf-8")

    db.session.commit()
