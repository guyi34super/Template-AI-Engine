"""
Template engine service — CRUD + versioning + schema management (Section 5.2).

Provides template lifecycle operations backed by PostgreSQL (or in-memory fallback).
"""
from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.db import is_async_db, get_sync_session

logger = logging.getLogger(__name__)

# In-memory fallback store
_inmemory_templates: dict[str, dict] = {}
_REGISTRY_PATH = Path("templates/registry.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> None:
    """Seed in-memory store from registry.json (dev mode only)."""
    if _inmemory_templates:
        return
    if _REGISTRY_PATH.exists():
        try:
            data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
            templates = data if isinstance(data, list) else data.get("templates", [])
            for t in templates:
                tid = t.get("id", str(uuid.uuid4()))
                _inmemory_templates[tid] = {
                    "id": tid,
                    "name": t.get("name", "Unnamed"),
                    "description": t.get("description", ""),
                    "version": t.get("version", 1),
                    "schema_json": t.get("fields", t.get("schema_json")),
                    "status": t.get("status", "published"),
                    "created_by": None,
                    "created_at": _now(),
                    "updated_at": None,
                    "published_at": _now() if t.get("status") == "published" else None,
                }
            logger.info("Loaded %d templates from registry.json", len(_inmemory_templates))
        except Exception as exc:
            logger.warning("Failed to load registry.json: %s", exc)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def list_templates(*, status: str | None = None, search: str | None = None) -> list[dict]:
    if is_async_db():
        from core.models import Template
        with get_sync_session() as session:
            q = session.query(Template).filter(Template.deleted_at.is_(None))
            if status:
                q = q.filter(Template.status == status)
            if search:
                q = q.filter(Template.name.ilike(f"%{search}%"))
            return [_orm_to_dict(t) for t in q.order_by(Template.created_at.desc()).all()]
    else:
        _load_registry()
        results = list(_inmemory_templates.values())
        if status:
            results = [t for t in results if t.get("status") == status]
        if search:
            results = [t for t in results if search.lower() in t.get("name", "").lower()]
        return results


def get_template(template_id: str) -> dict | None:
    if is_async_db():
        from core.models import Template
        with get_sync_session() as session:
            t = session.query(Template).filter(Template.id == template_id, Template.deleted_at.is_(None)).first()
            return _orm_to_dict(t) if t else None
    else:
        _load_registry()
        return _inmemory_templates.get(template_id)


def create_template(name: str, description: str = "", schema_json: Any = None, created_by: str | None = None) -> dict:
    tid = str(uuid.uuid4())
    if is_async_db():
        from core.models import Template
        with get_sync_session() as session:
            t = Template(id=tid, name=name, description=description, schema_json=schema_json, created_by=created_by)
            session.add(t)
            session.commit()
            session.refresh(t)
            return _orm_to_dict(t)
    else:
        _load_registry()
        doc = {
            "id": tid, "name": name, "description": description,
            "version": 1, "schema_json": schema_json, "status": "draft",
            "created_by": created_by, "created_at": _now(), "updated_at": None, "published_at": None,
        }
        _inmemory_templates[tid] = doc
        return doc


def update_template(template_id: str, *, name: str | None = None, description: str | None = None, schema_json: Any = None) -> dict | None:
    if is_async_db():
        from core.models import Template
        with get_sync_session() as session:
            t = session.query(Template).filter(Template.id == template_id, Template.deleted_at.is_(None)).first()
            if not t:
                return None
            if name is not None:
                t.name = name
            if description is not None:
                t.description = description
            if schema_json is not None:
                t.schema_json = schema_json
            t.version = (t.version or 1) + 1
            t.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(t)
            return _orm_to_dict(t)
    else:
        _load_registry()
        doc = _inmemory_templates.get(template_id)
        if not doc:
            return None
        if name is not None:
            doc["name"] = name
        if description is not None:
            doc["description"] = description
        if schema_json is not None:
            doc["schema_json"] = schema_json
        doc["version"] = doc.get("version", 1) + 1
        doc["updated_at"] = _now()
        return doc


def delete_template(template_id: str) -> bool:
    if is_async_db():
        from core.models import Template
        with get_sync_session() as session:
            t = session.query(Template).filter(Template.id == template_id).first()
            if not t:
                return False
            t.deleted_at = datetime.now(timezone.utc)
            session.commit()
            return True
    else:
        return _inmemory_templates.pop(template_id, None) is not None


def publish_template(template_id: str) -> dict | None:
    if is_async_db():
        from core.models import Template
        with get_sync_session() as session:
            t = session.query(Template).filter(Template.id == template_id).first()
            if not t:
                return None
            t.status = "published"
            t.published_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(t)
            return _orm_to_dict(t)
    else:
        doc = _inmemory_templates.get(template_id)
        if not doc:
            return None
        doc["status"] = "published"
        doc["published_at"] = _now()
        return doc


# ---------------------------------------------------------------------------
# Template fields (sub-resource)
# ---------------------------------------------------------------------------
def list_template_fields(template_id: str) -> list[dict]:
    if is_async_db():
        from core.models import TemplateField
        with get_sync_session() as session:
            fields = session.query(TemplateField).filter(TemplateField.template_id == template_id).order_by(TemplateField.sort_order).all()
            return [_field_to_dict(f) for f in fields]
    else:
        doc = _inmemory_templates.get(template_id, {})
        return doc.get("schema_json", []) if isinstance(doc.get("schema_json"), list) else []


def add_template_field(template_id: str, name: str, field_type: str = "text", required: bool = False, regex_pattern: str | None = None, description: str | None = None, sort_order: int = 0) -> dict:
    fid = str(uuid.uuid4())
    if is_async_db():
        from core.models import TemplateField
        with get_sync_session() as session:
            f = TemplateField(id=fid, template_id=template_id, name=name, type=field_type, required=required, regex_pattern=regex_pattern, description=description, sort_order=sort_order)
            session.add(f)
            session.commit()
            session.refresh(f)
            return _field_to_dict(f)
    return {"id": fid, "template_id": template_id, "name": name, "type": field_type, "required": required}


# ---------------------------------------------------------------------------
# ORM → dict converters
# ---------------------------------------------------------------------------
def _orm_to_dict(t) -> dict:
    return {
        "id": t.id, "name": t.name, "description": t.description,
        "version": t.version, "schema_json": t.schema_json,
        "status": t.status, "created_by": t.created_by,
        "created_at": str(t.created_at), "updated_at": str(t.updated_at) if t.updated_at else None,
        "published_at": str(t.published_at) if t.published_at else None,
    }


def _field_to_dict(f) -> dict:
    return {
        "id": f.id, "template_id": f.template_id, "name": f.name,
        "type": f.type, "required": f.required, "regex_pattern": f.regex_pattern,
        "description": f.description, "sort_order": f.sort_order,
    }
