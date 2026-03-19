"""
Session Store - manages chat sessions and file structure caches
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..models import ChatSession, ChatMessage, FileStructureCache


class SessionStore:
    """Store for chat sessions and file structure caches"""
    
    def __init__(self, db_path: str = "power_memory/data/sessions.db"):
        """Initialize session store"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Chat sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Chat messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
            )
        """)
        
        # File structure cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_structure_cache (
                cache_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                structure_hash TEXT NOT NULL,
                column_schema TEXT NOT NULL,
                sample_data TEXT NOT NULL,
                total_records INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                usage_count INTEGER DEFAULT 0,
                file_paths TEXT
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON chat_sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_session ON chat_messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_user ON file_structure_cache(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_hash ON file_structure_cache(structure_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_type ON file_structure_cache(file_type)")
        
        conn.commit()
        conn.close()
    
    # ========== Chat Session Methods ==========
    
    def create_session(self, session: ChatSession) -> bool:
        """Create a new chat session"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO chat_sessions 
                (session_id, user_id, started_at, last_activity, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.user_id,
                session.started_at.isoformat(),
                session.last_activity.isoformat(),
                json.dumps(session.metadata)
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating session: {e}")
            return False
        finally:
            conn.close()
    
    def add_message(self, session_id: str, message: ChatMessage) -> bool:
        """Add a message to a session"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO chat_messages 
                (session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                message.role,
                message.content,
                message.timestamp.isoformat(),
                json.dumps(message.metadata)
            ))
            
            # Update last_activity
            cursor.execute("""
                UPDATE chat_sessions 
                SET last_activity = ?
                WHERE session_id = ?
            """, (message.timestamp.isoformat(), session_id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding message: {e}")
            return False
        finally:
            conn.close()
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session with all messages"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,))
        session_row = cursor.fetchone()
        
        if not session_row:
            conn.close()
            return None
        
        cursor.execute("""
            SELECT * FROM chat_messages 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
        message_rows = cursor.fetchall()
        conn.close()
        
        messages = [
            ChatMessage(
                role=row['role'],
                content=row['content'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )
            for row in message_rows
        ]
        
        return ChatSession(
            session_id=session_row['session_id'],
            user_id=session_row['user_id'],
            messages=messages,
            started_at=datetime.fromisoformat(session_row['started_at']),
            last_activity=datetime.fromisoformat(session_row['last_activity']),
            metadata=json.loads(session_row['metadata']) if session_row['metadata'] else {}
        )
    
    def get_user_sessions(self, user_id: str, limit: int = 50) -> List[ChatSession]:
        """Get all sessions for a user"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM chat_sessions 
            WHERE user_id = ? 
            ORDER BY last_activity DESC 
            LIMIT ?
        """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        sessions = []
        for row in rows:
            session = self.get_session(row['session_id'])
            if session:
                sessions.append(session)
        
        return sessions
    
    # ========== File Structure Cache Methods ==========
    
    def create_file_cache(self, cache: FileStructureCache) -> bool:
        """Create a file structure cache entry"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO file_structure_cache 
                (cache_id, user_id, file_type, structure_hash, column_schema, 
                 sample_data, total_records, created_at, last_used, usage_count, file_paths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cache.cache_id,
                cache.user_id,
                cache.file_type,
                cache.structure_hash,
                json.dumps(cache.column_schema),
                json.dumps(cache.sample_data),
                cache.total_records,
                cache.created_at.isoformat(),
                cache.last_used.isoformat(),
                cache.usage_count,
                json.dumps(cache.file_paths)
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating file cache: {e}")
            return False
        finally:
            conn.close()
    
    def find_file_cache(
        self, 
        user_id: str, 
        structure_hash: str, 
        file_type: Optional[str] = None
    ) -> Optional[FileStructureCache]:
        """Find a cached file structure by hash"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM file_structure_cache 
            WHERE user_id = ? AND structure_hash = ?
        """
        params = [user_id, structure_hash]
        
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
        
        query += " ORDER BY last_used DESC LIMIT 1"
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return FileStructureCache(
            cache_id=row['cache_id'],
            user_id=row['user_id'],
            file_type=row['file_type'],
            structure_hash=row['structure_hash'],
            column_schema=json.loads(row['column_schema']),
            sample_data=json.loads(row['sample_data']),
            total_records=row['total_records'],
            created_at=datetime.fromisoformat(row['created_at']),
            last_used=datetime.fromisoformat(row['last_used']),
            usage_count=row['usage_count'],
            file_paths=json.loads(row['file_paths']) if row['file_paths'] else []
        )
    
    def update_file_cache_usage(self, cache_id: str, file_path: str):
        """Update cache usage statistics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get current file_paths
        cursor.execute("SELECT file_paths FROM file_structure_cache WHERE cache_id = ?", (cache_id,))
        row = cursor.fetchone()
        
        if row:
            file_paths = json.loads(row[0]) if row[0] else []
            if file_path not in file_paths:
                file_paths.append(file_path)
            
            cursor.execute("""
                UPDATE file_structure_cache 
                SET last_used = ?, usage_count = usage_count + 1, file_paths = ?
                WHERE cache_id = ?
            """, (datetime.utcnow().isoformat(), json.dumps(file_paths), cache_id))
            
            conn.commit()
        
        conn.close()
    
    def get_user_file_caches(self, user_id: str, limit: int = 20) -> List[FileStructureCache]:
        """Get all file caches for a user"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM file_structure_cache 
            WHERE user_id = ? 
            ORDER BY usage_count DESC, last_used DESC 
            LIMIT ?
        """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            FileStructureCache(
                cache_id=row['cache_id'],
                user_id=row['user_id'],
                file_type=row['file_type'],
                structure_hash=row['structure_hash'],
                column_schema=json.loads(row['column_schema']),
                sample_data=json.loads(row['sample_data']),
                total_records=row['total_records'],
                created_at=datetime.fromisoformat(row['created_at']),
                last_used=datetime.fromisoformat(row['last_used']),
                usage_count=row['usage_count'],
                file_paths=json.loads(row['file_paths']) if row['file_paths'] else []
            )
            for row in rows
        ]
