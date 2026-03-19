"""
SQLAlchemy ORM models for AI-RAG Engine.
All tables use UUID PKs, created_at / updated_at, and soft-delete via deleted_at.
Covers Section 7.1 of the architecture spec (11 core tables).
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, Index, Numeric,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import uuid as _uuid


def _uuid4() -> str:
    return str(_uuid.uuid4())


# ────────────────────────────────────────────────────────────────────
# 1. users
# ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="editor")  # viewer | editor | admin | system
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_login = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    sessions = relationship("SessionRecord", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user")
    audit_events = relationship("AuditEvent", back_populates="user")


# ────────────────────────────────────────────────────────────────────
# 2. sessions  (JWT revocation / auth sessions)
# ────────────────────────────────────────────────────────────────────
class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_uuid4)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    jwt_jti = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="sessions")


# ────────────────────────────────────────────────────────────────────
# 3. templates
# ────────────────────────────────────────────────────────────────────
class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=_uuid4)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1)
    schema_json = Column(JSON, nullable=True)
    status = Column(String(20), default="draft")  # draft | published
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    published_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    fields = relationship("TemplateField", back_populates="template", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="template")


# ────────────────────────────────────────────────────────────────────
# 4. template_fields
# ────────────────────────────────────────────────────────────────────
class TemplateField(Base):
    __tablename__ = "template_fields"

    id = Column(String, primary_key=True, default=_uuid4)
    template_id = Column(String, ForeignKey("templates.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    type = Column(String(30), nullable=False, default="text")
    required = Column(Boolean, default=False)
    regex_pattern = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    enum_values = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    template = relationship("Template", back_populates="fields")


# ────────────────────────────────────────────────────────────────────
# 5. documents
# ────────────────────────────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid4)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    template_id = Column(String, ForeignKey("templates.id"), nullable=True, index=True)
    name = Column(String(500), nullable=False)
    mime = Column(String(100), nullable=True)
    raw_file_path = Column(Text, nullable=True)
    extracted_json = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending | processing | complete | failed
    sha256 = Column(String(64), nullable=True, index=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="documents")
    template = relationship("Template", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    extraction_jobs = relationship("ExtractionJob", back_populates="document", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="document", cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────────────
# 6. chunks  (for vector search)
# ────────────────────────────────────────────────────────────────────
class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=_uuid4)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    page = Column(Integer, nullable=True)
    chunk_index = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    chunk_hash = Column(String(64), nullable=True, index=True)
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="chunks")


# ────────────────────────────────────────────────────────────────────
# 7. extraction_jobs
# ────────────────────────────────────────────────────────────────────
class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id = Column(String, primary_key=True, default=_uuid4)
    document_id = Column(String, ForeignKey("documents.id"), nullable=True, index=True)
    status = Column(String(20), default="pending")  # pending | processing | complete | failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="extraction_jobs")


# ────────────────────────────────────────────────────────────────────
# 8. validation_results
# ────────────────────────────────────────────────────────────────────
class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(String, primary_key=True, default=_uuid4)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    field_name = Column(String(200), nullable=False)
    status = Column(String(10), nullable=False)  # pass | fail | warning
    value = Column(Text, nullable=True)
    cleaned_value = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    rule_violated = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="validation_results")


# ────────────────────────────────────────────────────────────────────
# 9. mapping_configs
# ────────────────────────────────────────────────────────────────────
class MappingConfig(Base):
    __tablename__ = "mapping_configs"

    id = Column(String, primary_key=True, default=_uuid4)
    source_schema = Column(JSON, nullable=False)
    target_schema = Column(JSON, nullable=False)
    mappings_json = Column(JSON, nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# ────────────────────────────────────────────────────────────────────
# 10. audit_events
# ────────────────────────────────────────────────────────────────────
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, default=_uuid4)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(200), nullable=True)
    payload_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_events")


# ────────────────────────────────────────────────────────────────────
# 11. memory_entries  (Supermemory reference records)
# ────────────────────────────────────────────────────────────────────
class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id = Column(String, primary_key=True, default=_uuid4)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    memory_id = Column(String(200), nullable=True)  # external Supermemory ID
    memory_type = Column(String(30), nullable=False, default="general")  # general | fact | preference | correction
    context_summary = Column(Text, nullable=True)
    embedding_id = Column(String(200), nullable=True)  # reference to vector store entry
    keywords = Column(JSON, nullable=True)  # extracted keyword array
    importance_score = Column(Float, default=0.5)  # 0.0–1.0
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    keyword_entries = relationship("MemoryKeywordIndex", back_populates="memory_entry", cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────────────
# 11b. memory_keyword_index  (inverted keyword → memory lookup)
# ────────────────────────────────────────────────────────────────────
class MemoryKeywordIndex(Base):
    __tablename__ = "memory_keyword_index"

    id = Column(String, primary_key=True, default=_uuid4)
    memory_id = Column(String, ForeignKey("memory_entries.id"), nullable=False, index=True)
    keyword = Column(String(200), nullable=False, index=True)
    tf_score = Column(Float, default=0.0)  # term frequency
    created_at = Column(DateTime, server_default=func.now())

    memory_entry = relationship("MemoryEntry", back_populates="keyword_entries")

    __table_args__ = (
        Index("ix_memory_keyword_lookup", "keyword", "memory_id"),
    )


# ────────────────────────────────────────────────────────────────────
# 12. export_jobs
# ────────────────────────────────────────────────────────────────────
class ExportJob(Base):
    __tablename__ = "export_jobs"

    id = Column(String, primary_key=True, default=_uuid4)
    document_id = Column(String, ForeignKey("documents.id"), nullable=True, index=True)
    format = Column(String(10), nullable=False)  # pdf | xlsx | csv | txt | database
    status = Column(String(20), default="pending")  # pending | processing | complete | failed
    file_path = Column(Text, nullable=True)
    db_target_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
