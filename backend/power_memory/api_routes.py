"""
PowerMemory API Routes
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import will be added to api_server.py
# from power_memory import PowerMemoryEngine

router = APIRouter(prefix="/memory", tags=["PowerMemory"])


# ========== Request/Response Models ==========

class CreateSessionRequest(BaseModel):
    user_id: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AddMessageRequest(BaseModel):
    session_id: str
    role: str  # user, assistant, system
    content: str
    extract_memories: bool = True
    user_id: Optional[str] = None


class SearchMemoriesRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None


class UpdateMemoryRequest(BaseModel):
    old_memory_id: str
    new_title: str
    new_body: str
    user_id: Optional[str] = None


class FileAnalysisRequest(BaseModel):
    user_id: str


class ManipulationStrategyRequest(BaseModel):
    cache_id: str
    query: str


class RetrieveContextRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    question_date: Optional[str] = None  # ISO format
    max_memories: int = 10


# ========== API Endpoints ==========

@router.post("/session/create")
async def create_session(request: CreateSessionRequest):
    """Create a new chat session"""
    try:
        from api_server import power_memory
        
        session_id = power_memory.create_session(
            user_id=request.user_id,
            metadata=request.metadata
        )
        
        return {
            "success": True,
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/message")
async def add_message(request: AddMessageRequest):
    """Add a message to session and extract memories"""
    try:
        from api_server import power_memory
        
        result = power_memory.add_message(
            session_id=request.session_id,
            role=request.role,
            content=request.content,
            extract_memories=request.extract_memories,
            user_id=request.user_id
        )
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details with all messages"""
    try:
        from api_server import power_memory
        
        session = power_memory.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "success": True,
            "session": session.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/user/{user_id}")
async def get_user_sessions(user_id: str, limit: int = 50):
    """Get all sessions for a user"""
    try:
        from api_server import power_memory
        
        sessions = power_memory.get_user_sessions(user_id, limit)
        
        return {
            "success": True,
            "sessions": [s.dict() for s in sessions],
            "total": len(sessions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/ingest")
async def ingest_session(session_id: str, user_id: str, extract_memories: bool = True):
    """Ingest complete session and extract memories"""
    try:
        from api_server import power_memory
        
        result = power_memory.ingest_session(
            session_id=session_id,
            user_id=user_id,
            extract_memories=extract_memories
        )
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/search")
async def search_memories(request: SearchMemoriesRequest):
    """Search memories semantically"""
    try:
        from api_server import power_memory
        
        memories = power_memory.search_memories(
            query=request.query,
            user_id=request.user_id,
            top_k=request.top_k,
            filters=request.filters
        )
        
        return {
            "success": True,
            "memories": [m.dict() for m in memories],
            "total": len(memories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/update")
async def update_memory(request: UpdateMemoryRequest):
    """Update a memory (creates new version)"""
    try:
        from api_server import power_memory
        
        new_memory = power_memory.update_memory(
            old_memory_id=request.old_memory_id,
            new_title=request.new_title,
            new_body=request.new_body,
            user_id=request.user_id
        )
        
        return {
            "success": True,
            "new_memory": new_memory.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories/{memory_id}/history")
async def get_memory_history(memory_id: str):
    """Get update history for a memory"""
    try:
        from api_server import power_memory
        
        history = power_memory.memory_store.get_memory_history(memory_id)
        
        return {
            "success": True,
            "history": [m.dict() for m in history],
            "versions": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file/analyze")
async def analyze_file(
    user_id: str,
    file_path: str,
    data: List[Dict[str, Any]]
):
    """Analyze file structure and check cache"""
    try:
        from api_server import power_memory
        
        cache = power_memory.analyze_file(
            data=data,
            file_path=file_path,
            user_id=user_id
        )
        
        return {
            "success": True,
            "cache": cache.dict(),
            "is_cached": cache.usage_count > 1,
            "message": f"Structure used {cache.usage_count} times before" if cache.usage_count > 1 else "New structure detected"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file/strategy")
async def get_manipulation_strategy(cache_id: str, query: str):
    """Get intelligent manipulation strategy for cached structure"""
    try:
        from api_server import power_memory
        
        # Get cache first
        # TODO: Add method to get cache by ID
        
        return {
            "success": True,
            "message": "Strategy generation not yet implemented"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/caches/{user_id}")
async def get_user_caches(user_id: str):
    """Get all cached file structures for a user"""
    try:
        from api_server import power_memory
        
        caches = power_memory.get_user_file_caches(user_id)
        
        return {
            "success": True,
            "caches": [c.dict() for c in caches],
            "total": len(caches)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve")
async def retrieve_context(request: RetrieveContextRequest):
    """Hybrid retrieval: get memories and source chunks"""
    try:
        from api_server import power_memory
        
        question_date = None
        if request.question_date:
            question_date = datetime.fromisoformat(request.question_date)
        
        context = power_memory.retrieve_context(
            query=request.query,
            user_id=request.user_id,
            question_date=question_date,
            max_memories=request.max_memories
        )
        
        return {
            "success": True,
            **context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(user_id: Optional[str] = None):
    """Get PowerMemory statistics"""
    try:
        from api_server import power_memory
        
        stats = power_memory.get_stats(user_id)
        
        return {
            "success": True,
            **stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
