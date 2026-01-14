"""
PowerMemory Engine - Main orchestrator for memory management
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .models import (
    Memory, Chunk, ChatSession, ChatMessage, 
    FileStructureCache, MemoryRelation, RelationType, MemoryStatus
)
from .stores import MemoryGraphStore, SessionStore
from .services import Chunker, MemoryExtractor, FileStructureIntelligence
from core.vdb import VDB


class PowerMemoryEngine:
    """
    PowerMemory Engine - Advanced memory system for LLM assistants
    
    Features:
    - Multi-LLM memory management
    - Chat session tracking
    - Intelligent file structure caching
    - Hybrid memory retrieval
    - Temporal reasoning
    """
    
    def __init__(
        self,
        llm,
        vector_db: Optional[VDB] = None,
        embedding_func=None,
        memory_db_path: str = "power_memory/data/memory_graph.db",
        session_db_path: str = "power_memory/data/sessions.db"
    ):
        """
        Initialize PowerMemory Engine
        
        Args:
            llm: LLM instance for memory extraction and reasoning
            vector_db: Vector database for semantic search
            embedding_func: Embedding function for vectorization
            memory_db_path: Path to memory graph database
            session_db_path: Path to session database
        """
        self.llm = llm
        self.vector_db = vector_db
        self.embedding_func = embedding_func
        
        # Initialize stores
        self.memory_store = MemoryGraphStore(memory_db_path)
        self.session_store = SessionStore(session_db_path)
        
        # Initialize services
        self.chunker = Chunker(max_tokens=800)
        self.memory_extractor = MemoryExtractor(llm)
        self.file_intelligence = FileStructureIntelligence(self.session_store)
        
        print("✅ PowerMemory Engine initialized")
    
    # ========== Session Management ==========
    
    def create_session(self, user_id: str, metadata: Optional[Dict] = None) -> str:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {}
        )
        self.session_store.create_session(session)
        return session_id
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        extract_memories: bool = True,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add message to session and optionally extract memories
        
        Args:
            session_id: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            extract_memories: Whether to extract memories from message
            user_id: User identifier
        
        Returns:
            Dict with message info and extracted memories
        """
        message = ChatMessage(role=role, content=content)
        self.session_store.add_message(session_id, message)
        
        result = {
            'message_added': True,
            'memories_extracted': 0
        }
        
        # Extract memories if requested and significant content
        if extract_memories and len(content) > 50:
            # Create chunk from message
            chunk = Chunk(
                chunk_id=f"{session_id}_msg_{uuid.uuid4()}",
                session_id=session_id,
                text=f"{role}: {content}",
                start_idx=0,
                end_idx=0,
                document_date=message.timestamp,
                tokens=self.chunker.count_tokens(content)
            )
            
            # Extract memories
            memories = self.memory_extractor.extract_memories(
                chunk=chunk,
                user_id=user_id
            )
            
            # Store memories
            for memory in memories:
                self.memory_store.create_memory(memory)
                
                # Vectorize if vector DB available
                if self.vector_db and self.embedding_func:
                    self._vectorize_memory(memory)
            
            result['memories_extracted'] = len(memories)
            result['memories'] = [m.dict() for m in memories]
        
        return result
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get chat session with all messages"""
        return self.session_store.get_session(session_id)
    
    def get_user_sessions(self, user_id: str, limit: int = 50) -> List[ChatSession]:
        """Get all sessions for a user"""
        return self.session_store.get_user_sessions(user_id, limit)
    
    # ========== Memory Management ==========
    
    def ingest_session(
        self,
        session_id: str,
        user_id: str,
        extract_memories: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest a complete session and extract memories
        
        Args:
            session_id: Session to ingest
            user_id: User identifier
            extract_memories: Whether to extract memories
        
        Returns:
            Ingestion statistics
        """
        session = self.session_store.get_session(session_id)
        if not session:
            return {'error': 'Session not found'}
        
        # Convert messages to dict format for chunker
        messages = [
            {'role': msg.role, 'content': msg.content}
            for msg in session.messages
        ]
        
        # Chunk the session
        chunks = self.chunker.chunk_session(
            messages=messages,
            session_id=session_id,
            document_date=session.started_at
        )
        
        print(f"   📦 Created {len(chunks)} chunks")
        
        memories_extracted = []
        
        if extract_memories:
            # Extract memories from each chunk
            for chunk in chunks:
                memories = self.memory_extractor.extract_memories(
                    chunk=chunk,
                    user_id=user_id
                )
                
                # Store memories
                for memory in memories:
                    self.memory_store.create_memory(memory)
                    
                    # Vectorize
                    if self.vector_db and self.embedding_func:
                        self._vectorize_memory(memory)
                    
                    memories_extracted.append(memory)
            
            print(f"   🧠 Extracted {len(memories_extracted)} memories")
        
        return {
            'session_id': session_id,
            'chunks_created': len(chunks),
            'memories_extracted': len(memories_extracted),
            'memories': [m.dict() for m in memories_extracted]
        }
    
    def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Memory]:
        """
        Search memories semantically
        
        Args:
            query: Search query
            user_id: Filter by user
            top_k: Number of results
            filters: Additional filters
        
        Returns:
            List of matching memories
        """
        if not self.vector_db or not self.embedding_func:
            # Fallback to text search
            return self.memory_store.search_memories(
                user_id=user_id,
                title_query=query,
                limit=top_k
            )
        
        # Vector search
        # TODO: Implement vector search when vector DB is configured
        # For now, fallback to text search
        return self.memory_store.search_memories(
            user_id=user_id,
            title_query=query,
            limit=top_k
        )
    
    def update_memory(
        self,
        old_memory_id: str,
        new_title: str,
        new_body: str,
        user_id: Optional[str] = None
    ) -> Memory:
        """
        Update a memory (creates new version and deprecates old)
        
        Args:
            old_memory_id: Memory to update
            new_title: Updated title
            new_body: Updated body
            user_id: User identifier
        
        Returns:
            New memory version
        """
        old_memory = self.memory_store.get_memory(old_memory_id)
        if not old_memory:
            raise ValueError("Memory not found")
        
        # Create new memory version
        new_memory = Memory(
            memory_id=str(uuid.uuid4()),
            title=new_title,
            body=new_body,
            document_date=datetime.utcnow(),
            event_dates=old_memory.event_dates,
            source_chunk=old_memory.source_chunk,
            status=MemoryStatus.ACTIVE,
            tags=old_memory.tags,
            confidence=old_memory.confidence,
            user_id=user_id or old_memory.user_id,
            session_id=old_memory.session_id
        )
        
        # Store new memory
        self.memory_store.create_memory(new_memory)
        
        # Create update relation
        relation = MemoryRelation(
            from_id=old_memory_id,
            to_id=new_memory.memory_id,
            relation_type=RelationType.UPDATES
        )
        self.memory_store.create_relation(relation)
        
        # Deprecate old memory
        self.memory_store.update_memory_status(
            old_memory_id,
            MemoryStatus.DEPRECATED,
            replaced_by=new_memory.memory_id
        )
        
        # Vectorize new memory
        if self.vector_db and self.embedding_func:
            self._vectorize_memory(new_memory)
        
        return new_memory
    
    # ========== File Structure Intelligence ==========
    
    def analyze_file(
        self,
        data: List[Dict[str, Any]],
        file_path: str,
        user_id: str = "global"
    ) -> FileStructureCache:
        """
        Analyze file structure and check cache (GLOBAL by default)
        
        Args:
            data: File data records
            file_path: Path to file
            user_id: User ID (default: "global" for cross-user caching)
        
        Returns cached structure if similar file was uploaded before by ANY user
        """
        return self.file_intelligence.analyze_file_structure(
            data=data,
            file_path=file_path,
            user_id=user_id
        )
    
    def get_manipulation_strategy(
        self,
        cache: FileStructureCache,
        query: str
    ) -> Dict[str, Any]:
        """Get intelligent manipulation strategy using cached structure"""
        return self.file_intelligence.get_manipulation_context(
            cache=cache,
            query=query,
            llm=self.llm
        )
    
    def get_user_file_caches(self, user_id: str) -> List[FileStructureCache]:
        """Get all cached file structures for a user"""
        return self.file_intelligence.get_cached_structures(user_id)
    
    # ========== Hybrid Retrieval ==========
    
    def retrieve_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        question_date: Optional[datetime] = None,
        max_memories: int = 10
    ) -> Dict[str, Any]:
        """
        Hybrid retrieval: search memories and fetch source chunks
        
        Args:
            query: User query
            user_id: Filter by user
            question_date: Reference date for temporal reasoning
            max_memories: Maximum memories to retrieve
        
        Returns:
            Context with memories and source chunks
        """
        # Search memories
        memories = self.search_memories(
            query=query,
            user_id=user_id,
            top_k=max_memories
        )
        
        # TODO: Fetch and rank source chunks
        # For now, return memories only
        
        return {
            'memories': [m.dict() for m in memories],
            'chunks': [],  # TODO: implement chunk fetching
            'question_date': question_date.isoformat() if question_date else None
        }
    
    # ========== Private Methods ==========
    
    def _vectorize_memory(self, memory: Memory):
        """Vectorize a memory and store in vector DB"""
        if not self.vector_db or not self.embedding_func:
            return
        
        # Create embedding text (title + body)
        text = f"{memory.title}. {memory.body}"
        
        # TODO: Implement vectorization
        # embedding = self.embedding_func(text)
        # self.vector_db.add(memory.memory_id, embedding, metadata)
        pass
    
    # ========== Statistics ==========
    
    def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get PowerMemory statistics"""
        stats = {
            'total_sessions': 0,
            'total_memories': 0,
            'cached_structures': 0
        }
        
        if user_id:
            sessions = self.session_store.get_user_sessions(user_id, limit=1000)
            memories = self.memory_store.search_memories(user_id=user_id, limit=10000)
            caches = self.file_intelligence.get_cached_structures(user_id)
            
            stats['total_sessions'] = len(sessions)
            stats['total_memories'] = len(memories)
            stats['cached_structures'] = len(caches)
        
        return stats
