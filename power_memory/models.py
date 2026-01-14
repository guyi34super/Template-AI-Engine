"""
Data models for PowerMemory
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MemoryStatus(str, Enum):
    """Status of a memory node"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DERIVED = "derived"


class RelationType(str, Enum):
    """Types of relations between memory nodes"""
    UPDATES = "updates"
    EXTENDS = "extends"
    DERIVES = "derives"
    CONTRADICTS = "contradicts"


class Chunk(BaseModel):
    """Represents a chunk of text from a session or document"""
    chunk_id: str
    session_id: str
    text: str
    start_idx: int
    end_idx: int
    document_date: datetime
    tokens: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Memory(BaseModel):
    """Atomic memory extracted from a chunk"""
    memory_id: str
    title: str
    body: str
    document_date: datetime
    event_dates: List[str] = Field(default_factory=list)
    source_chunk: str
    status: MemoryStatus = MemoryStatus.ACTIVE
    vector_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    replaced_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryRelation(BaseModel):
    """Relation between two memory nodes"""
    from_id: str
    to_id: str
    relation_type: RelationType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """A single message in a chat session"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    """A chat session with multiple messages"""
    session_id: str
    user_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FileStructureCache(BaseModel):
    """Cached file structure for quick manipulation"""
    cache_id: str
    user_id: str
    file_type: str  # jsonl, json, csv, xlsx, etc.
    structure_hash: str  # hash of column names and types
    column_schema: Dict[str, str]  # column_name -> type
    sample_data: List[Dict[str, Any]]  # first 3-5 records
    total_records: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: datetime = Field(default_factory=datetime.utcnow)
    usage_count: int = 0
    file_paths: List[str] = Field(default_factory=list)  # files with this structure


class RetrievalContext(BaseModel):
    """Context retrieved for answering a query"""
    memories: List[Memory]
    chunks: List[Chunk]
    scores: List[float]
    question_date: Optional[datetime] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
