"""
Seed script — creates initial admin user + sample templates in the database.

Usage:
  cd backend
  python -m scripts.seed_database

Works with both PostgreSQL and SQLite fallback.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import is_async_db, get_sync_session, init_db
from core.auth import hash_password
import uuid
from datetime import datetime, timezone


def seed_admin():
    """Seed the default admin user."""
    if not is_async_db():
        print("  ⏭  Not using PostgreSQL — admin seeded in-memory by auth module")
        return
    from core.models import User
    with get_sync_session() as session:
        existing = session.query(User).filter(User.email == "admin@ai-rag.local").first()
        if existing:
            print("  ✓ Admin user already exists")
            return
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@ai-rag.local",
            password_hash=hash_password("Admin1234"),
            role="admin",
        )
        session.add(admin)
        session.commit()
        print("  ✓ Admin user created (admin@ai-rag.local / Admin1234)")


def seed_templates():
    """Seed sample templates."""
    from core.template_engine import create_template, list_templates, publish_template, add_template_field

    existing = list_templates()
    if existing:
        print(f"  ✓ {len(existing)} templates already present — skipping")
        return

    samples = [
        {
            "name": "Employee Profile",
            "description": "Standard employee information extraction template",
            "fields": [
                ("employee_id", "text", True, r"^\d{5,10}$"),
                ("first_name", "text", True, None),
                ("last_name", "text", True, None),
                ("email", "email", True, None),
                ("phone", "phone", False, None),
                ("hire_date", "date", True, None),
                ("department", "text", True, None),
                ("job_title", "text", True, None),
                ("salary", "number", False, None),
            ],
        },
        {
            "name": "Invoice",
            "description": "Standard invoice data extraction template",
            "fields": [
                ("invoice_number", "text", True, r"^INV-\d{6,}$"),
                ("vendor_name", "text", True, None),
                ("invoice_date", "date", True, None),
                ("due_date", "date", True, None),
                ("total_amount", "number", True, None),
                ("currency", "text", True, None),
                ("tax_amount", "number", False, None),
                ("line_items", "list", False, None),
            ],
        },
        {
            "name": "South African ID Document",
            "description": "SA identity document extraction with ZA-specific validations",
            "fields": [
                ("id_number", "id_number", True, r"^\d{13}$"),
                ("full_name", "text", True, None),
                ("date_of_birth", "date", True, None),
                ("nationality", "text", True, None),
                ("gender", "enum", True, None),
                ("issue_date", "date", False, None),
            ],
        },
    ]

    for tmpl in samples:
        t = create_template(tmpl["name"], tmpl["description"])
        for i, (name, ftype, req, pattern) in enumerate(tmpl["fields"]):
            add_template_field(t["id"], name=name, field_type=ftype, required=req, regex_pattern=pattern, sort_order=i)
        publish_template(t["id"])
        print(f"  ✓ Template '{tmpl['name']}' created + published ({len(tmpl['fields'])} fields)")


def main():
    print("=" * 50)
    print("AI-RAG Engine — Database Seed")
    print("=" * 50)

    # Ensure tables exist (SQLite only — PG uses Alembic)
    if not is_async_db():
        init_db()
        print("✓ SQLite database initialized")

    print("\n→ Seeding admin user...")
    seed_admin()

    print("\n→ Seeding templates...")
    seed_templates()

    print("\n✅ Seed complete!")


if __name__ == "__main__":
    main()
