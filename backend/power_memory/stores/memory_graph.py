"""
Memory Graph Store - manages memory nodes and relations
Uses SQLite with graph-like queries for simplicity and portability
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..models import Memory, MemoryRelation, MemoryStatus, RelationType


class MemoryGraphStore:
    """Graph store for memories and relations"""
    
    def __init__(self, db_path: str = "power_memory/data/memory_graph.db"):
        """Initialize memory graph store"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                document_date TEXT NOT NULL,
                event_dates TEXT,
                source_chunk TEXT,
                status TEXT DEFAULT 'active',
                vector_id TEXT,
                tags TEXT,
                confidence REAL DEFAULT 0.0,
                user_id TEXT,
                session_id TEXT,
                replaced_by TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (replaced_by) REFERENCES memories(memory_id)
            )
        """)
        
        # Relations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                metadata TEXT,
                FOREIGN KEY (from_id) REFERENCES memories(memory_id),
                FOREIGN KEY (to_id) REFERENCES memories(memory_id),
                UNIQUE(from_id, to_id, relation_type)
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON memories(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON memories(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON memories(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_date ON memories(document_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON memories(title)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_to ON relations(to_id)")
        
        conn.commit()
        conn.close()
    
    def create_memory(self, memory: Memory) -> bool:
        """Create a new memory node"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO memories 
                (memory_id, title, body, document_date, event_dates, source_chunk, 
                 status, vector_id, tags, confidence, user_id, session_id, 
                 replaced_by, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.memory_id,
                memory.title,
                memory.body,
                memory.document_date.isoformat(),
                json.dumps(memory.event_dates),
                memory.source_chunk,
                memory.status.value,
                memory.vector_id,
                json.dumps(memory.tags),
                memory.confidence,
                memory.user_id,
                memory.session_id,
                memory.replaced_by,
                memory.created_at.isoformat(),
                json.dumps(memory.metadata)
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating memory: {e}")
            return False
        finally:
            conn.close()
    
    def create_relation(self, relation: MemoryRelation) -> bool:
        """Create a relation between memories"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO relations 
                (from_id, to_id, relation_type, created_at, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                relation.from_id,
                relation.to_id,
                relation.relation_type.value,
                relation.created_at.isoformat(),
                relation.confidence,
                json.dumps(relation.metadata)
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating relation: {e}")
            return False
        finally:
            conn.close()
    
    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_memory(row)
    
    def get_latest_memory(self, title: str, user_id: Optional[str] = None) -> Optional[Memory]:
        """Get the latest active memory with a given title"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM memories 
            WHERE title = ? AND status = 'active'
        """
        params = [title]
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        query += " ORDER BY document_date DESC LIMIT 1"
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_memory(row)
    
    def search_memories(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        title_query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        limit: int = 50
    ) -> List[Memory]:
        """Search memories with filters"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if title_query:
            query += " AND title LIKE ?"
            params.append(f"%{title_query}%")
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY document_date DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        memories = [self._row_to_memory(row) for row in rows]
        
        # Filter by tags if specified
        if tags:
            memories = [m for m in memories if any(tag in m.tags for tag in tags)]
        
        return memories
    
    def get_memory_history(self, memory_id: str) -> List[Memory]:
        """Get update history for a memory (traverse updates chain)"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        history = []
        current_id = memory_id
        visited = set()
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            cursor.execute("SELECT * FROM memories WHERE memory_id = ?", (current_id,))
            row = cursor.fetchone()
            
            if not row:
                break
            
            memory = self._row_to_memory(row)
            history.append(memory)
            
            # Find what this memory updated (predecessor)
            cursor.execute("""
                SELECT from_id FROM relations 
                WHERE to_id = ? AND relation_type = 'updates'
            """, (current_id,))
            prev = cursor.fetchone()
            current_id = prev['from_id'] if prev else None
        
        conn.close()
        return history
    
    def update_memory_status(self, memory_id: str, status: MemoryStatus, replaced_by: Optional[str] = None):
        """Update memory status (e.g., mark as deprecated)"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE memories 
            SET status = ?, replaced_by = ?
            WHERE memory_id = ?
        """, (status.value, replaced_by, memory_id))
        
        conn.commit()
        conn.close()
    
    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert database row to Memory object"""
        return Memory(
            memory_id=row['memory_id'],
            title=row['title'],
            body=row['body'],
            document_date=datetime.fromisoformat(row['document_date']),
            event_dates=json.loads(row['event_dates']) if row['event_dates'] else [],
            source_chunk=row['source_chunk'],
            status=MemoryStatus(row['status']),
            vector_id=row['vector_id'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            confidence=row['confidence'],
            user_id=row['user_id'],
            session_id=row['session_id'],
            replaced_by=row['replaced_by'],
            created_at=datetime.fromisoformat(row['created_at']),
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
