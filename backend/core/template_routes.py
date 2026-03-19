"""
Template Engine API routes.
Template CRUD, field definitions, version control, and publish workflow.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import uuid
from pathlib import Path

router = APIRouter(prefix="/templates", tags=["Templates"])

# In-memory template store (replace with PostgreSQL in production)
_templates: Dict[str, dict] = {}

# Load templates from registry.json on startup
_registry_path = Path(__file__).parent.parent / "templates" / "registry.json"


def _load_registry():
    """Load templates from registry.json"""
    global _templates
    if _registry_path.exists():
        try:
            with open(_registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            for name, template_data in registry.items():
                template_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
                fields = []
                if isinstance(template_data, dict):
                    for i, (field_name, field_info) in enumerate(template_data.get("fields", {}).items()):
                        fields.append({
                            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}.{field_name}")),
                            "name": field_name,
                            "type": field_info.get("type", "text") if isinstance(field_info, dict) else "text",
                            "required": field_info.get("required", False) if isinstance(field_info, dict) else False,
                            "description": field_info.get("description", "") if isinstance(field_info, dict) else str(field_info),
                            "sort_order": i,
                        })
                _templates[template_id] = {
                    "id": template_id,
                    "name": name,
                    "description": template_data.get("description", f"{name} template") if isinstance(template_data, dict) else name,
                    "version": 1,
                    "status": "published",
                    "fields": fields,
                    "created_by": "system",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "published_at": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            print(f"Warning: Could not load registry.json: {e}")


_load_registry()


# ===== Models =====
class TemplateFieldCreate(BaseModel):
    name: str
    type: str = "text"
    required: bool = False
    regex_pattern: Optional[str] = None
    description: Optional[str] = None
    enum_values: Optional[List[str]] = None


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    fields: List[TemplateFieldCreate] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[List[TemplateFieldCreate]] = None


# ===== Endpoints =====
@router.get("")
async def list_templates():
    """List all templates (paginated)"""
    return list(_templates.values())


@router.post("", status_code=201)
async def create_template(req: TemplateCreate):
    """Create a new template"""
    template_id = str(uuid.uuid4())
    fields = [
        {
            "id": str(uuid.uuid4()),
            "name": f.name,
            "type": f.type,
            "required": f.required,
            "regex_pattern": f.regex_pattern,
            "description": f.description,
            "enum_values": f.enum_values,
            "sort_order": i,
        }
        for i, f in enumerate(req.fields)
    ]

    _templates[template_id] = {
        "id": template_id,
        "name": req.name,
        "description": req.description,
        "version": 1,
        "status": "draft",
        "fields": fields,
        "created_by": "user",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    return _templates[template_id]


@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get template by ID"""
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/{template_id}")
async def update_template(template_id: str, req: TemplateUpdate):
    """Update template (creates new version)"""
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if req.name:
        template["name"] = req.name
    if req.description is not None:
        template["description"] = req.description
    if req.fields is not None:
        template["fields"] = [
            {
                "id": str(uuid.uuid4()),
                "name": f.name,
                "type": f.type,
                "required": f.required,
                "regex_pattern": f.regex_pattern,
                "description": f.description,
                "sort_order": i,
            }
            for i, f in enumerate(req.fields)
        ]

    template["version"] += 1
    template["updated_at"] = datetime.utcnow().isoformat()
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str):
    """Soft-delete template"""
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")
    _templates[template_id]["deleted_at"] = datetime.utcnow().isoformat()
    del _templates[template_id]
    return None


@router.post("/{template_id}/publish")
async def publish_template(template_id: str):
    """Publish a draft template"""
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template["status"] = "published"
    template["published_at"] = datetime.utcnow().isoformat()
    return template


@router.get("/{template_id}/history")
async def get_template_history(template_id: str):
    """Get version history for a template"""
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "template_id": template_id,
        "current_version": template["version"],
        "history": [
            {
                "version": template["version"],
                "updated_at": template["updated_at"],
                "status": template["status"],
            }
        ],
    }
