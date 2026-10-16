from datetime import datetime

from flask_login import current_user

from app.excel_io import mapped_record
from app.extensions import db
from app.models import Activity, CustomerRequest, Deal, Lead, Organization, Person, User


def find_user(email):
    if not email:
        return current_user.id
    user = User.query.filter(User.email.ilike(email.strip())).first()
    return user.id if user else current_user.id


def find_org(name):
    if not name:
        return None
    org = Organization.query.filter(Organization.name.ilike(name.strip())).first()
    if org:
        return org
    org = Organization(name=name.strip(), owner_id=current_user.id)
    db.session.add(org)
    db.session.flush()
    return org


def find_person(name, email=None, org=None):
    if email:
        person = Person.query.filter(Person.email.ilike(email.strip())).first()
        if person:
            return person
    if name:
        q = Person.query.filter(Person.name.ilike(name.strip()))
        person = q.first()
        if person:
            return person
        person = Person(
            name=name.strip(),
            email=email or "",
            organization_id=org.id if org else None,
            owner_id=current_user.id,
        )
        db.session.add(person)
        db.session.flush()
        return person
    return None


def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def import_people(records, mapping, duplicate="skip"):
    created = updated = skipped = 0
    errors = []
    for i, raw in enumerate(records, start=2):
        data = mapped_record(raw, mapping)
        name = data.get("name")
        email = data.get("email", "")
        if not name:
            errors.append(f"Row {i}: name is required")
            continue
        existing = None
        if email:
            existing = Person.query.filter(Person.email.ilike(email)).first()
        if existing and duplicate == "skip":
            skipped += 1
            continue
        org = find_org(data.get("organization"))
        if existing and duplicate == "update":
            existing.name = name
            existing.phone = data.get("phone", existing.phone)
            existing.job_title = data.get("job_title", existing.job_title)
            if org:
                existing.organization_id = org.id
            updated += 1
        else:
            db.session.add(
                Person(
                    name=name,
                    email=email,
                    phone=data.get("phone", ""),
                    job_title=data.get("job_title", ""),
                    organization_id=org.id if org else None,
                    owner_id=find_user(data.get("owner_email")),
                )
            )
            created += 1
    db.session.commit()
    return created, updated, skipped, errors


def import_organizations(records, mapping, duplicate="skip"):
    created = updated = skipped = 0
    errors = []
    for i, raw in enumerate(records, start=2):
        data = mapped_record(raw, mapping)
        name = data.get("name")
        if not name:
            errors.append(f"Row {i}: name is required")
            continue
        existing = Organization.query.filter(Organization.name.ilike(name)).first()
        if existing and duplicate == "skip":
            skipped += 1
            continue
        if existing and duplicate == "update":
            existing.address = data.get("address", existing.address)
            existing.website = data.get("website", existing.website)
            existing.phone = data.get("phone", existing.phone)
            updated += 1
        else:
            db.session.add(
                Organization(
                    name=name,
                    address=data.get("address", ""),
                    website=data.get("website", ""),
                    phone=data.get("phone", ""),
                    owner_id=find_user(data.get("owner_email")),
                )
            )
            created += 1
    db.session.commit()
    return created, updated, skipped, errors


def import_deals(records, mapping, duplicate="skip"):
    created = updated = skipped = 0
    errors = []
    for i, raw in enumerate(records, start=2):
        data = mapped_record(raw, mapping)
        title = data.get("title")
        if not title:
            errors.append(f"Row {i}: title is required")
            continue
        existing = Deal.query.filter(Deal.title.ilike(title)).first()
        if existing and duplicate == "skip":
            skipped += 1
            continue
        org = find_org(data.get("organization"))
        person = find_person(data.get("contact_person"), org=org)
        try:
            value = float(data.get("value") or 0)
        except ValueError:
            errors.append(f"Row {i}: invalid value")
            continue
        stage = data.get("stage") or "Qualified"
        if stage not in Deal.STAGES:
            stage = "Qualified"
        payload = dict(
            title=title,
            value=value,
            currency=data.get("currency") or "LKR",
            stage=stage,
            status=data.get("status") or "open",
            organization_id=org.id if org else None,
            person_id=person.id if person else None,
            owner_id=find_user(data.get("owner_email")),
            expected_close_date=parse_date(data.get("expected_close_date")),
        )
        if existing and duplicate == "update":
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.session.add(Deal(**payload))
            created += 1
    db.session.commit()
    return created, updated, skipped, errors


def import_leads(records, mapping, duplicate="skip"):
    created = updated = skipped = 0
    errors = []
    for i, raw in enumerate(records, start=2):
        data = mapped_record(raw, mapping)
        title = data.get("title")
        if not title:
            errors.append(f"Row {i}: title is required")
            continue
        existing = Lead.query.filter(Lead.title.ilike(title)).first()
        if existing and duplicate == "skip":
            skipped += 1
            continue
        payload = dict(
            title=title,
            person_name=data.get("person_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            organization_name=data.get("organization_name", ""),
            source=data.get("source") or "import",
            status=data.get("status") or "new",
            owner_id=find_user(data.get("owner_email")),
        )
        if existing and duplicate == "update":
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.session.add(Lead(**payload))
            created += 1
    db.session.commit()
    return created, updated, skipped, errors


def import_activities(records, mapping, duplicate="skip"):
    created = skipped = 0
    updated = 0
    errors = []
    for i, raw in enumerate(records, start=2):
        data = mapped_record(raw, mapping)
        subject = data.get("subject")
        if not subject:
            errors.append(f"Row {i}: subject is required")
            continue
        org = find_org(data.get("organization"))
        person = find_person(data.get("person"), org=org)
        deal = None
        if data.get("deal"):
            deal = Deal.query.filter(Deal.title.ilike(data["deal"])).first()
        db.session.add(
            Activity(
                type=(data.get("type") or "task").lower(),
                subject=subject,
                due_at=parse_datetime(data.get("due_at")),
                done=str(data.get("done", "")).lower() in ("1", "true", "yes"),
                person_id=person.id if person else None,
                organization_id=org.id if org else None,
                deal_id=deal.id if deal else None,
                owner_id=find_user(data.get("owner_email")),
            )
        )
        created += 1
    db.session.commit()
    return created, updated, skipped, errors


def import_customers(records, mapping, duplicate="skip"):
    created = updated = skipped = 0
    errors = []
    for i, raw in enumerate(records, start=2):
        data = mapped_record(raw, mapping)
        if not data.get("customer_name") or not data.get("customer_email") or not data.get("title"):
            errors.append(f"Row {i}: customer_name, customer_email and title are required")
            continue
        existing = CustomerRequest.query.filter_by(
            customer_email=data["customer_email"], title=data["title"]
        ).first()
        if existing and duplicate == "skip":
            skipped += 1
            continue
        payload = dict(
            customer_name=data["customer_name"],
            customer_email=data["customer_email"],
            customer_phone=data.get("customer_phone", ""),
            organization_name=data.get("organization_name", ""),
            request_type=data.get("request_type") or "support",
            title=data["title"],
            description=data.get("description", ""),
            status=data.get("status") or "new",
        )
        if existing and duplicate == "update":
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.session.add(CustomerRequest(**payload))
            created += 1
    db.session.commit()
    return created, updated, skipped, errors
