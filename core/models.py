# aqee/core/models.py
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)          # uuid
    tenant_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    mime = Column(String)
    path = Column(Text, nullable=False)
    size_bytes = Column(Integer)
    sha256 = Column(String, index=True)
    status = Column(String, default="ready")       # queued|ready|failed
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True)          # uuid
    doc_id = Column(String, ForeignKey("documents.id"), index=True)
    tenant_id = Column(String, index=True)
    page = Column(Integer)
    start = Column(Integer)                         # char offsets within page/text block
    end = Column(Integer)
    chunk_id = Column(String, index=True)          # stable id for provenance
    chunk_hash = Column(String, index=True)
    text = Column(Text)
    quality_score = Column(Float)
    document = relationship("Document", back_populates="chunks")

class Template(Base):
    __tablename__ = "templates"
    id = Column(String, primary_key=True)          # uuid
    name = Column(String, index=True)
    source_doc_id = Column(String, nullable=True)
    header_json = Column(Text)                     # JSON string of canonical headers
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
