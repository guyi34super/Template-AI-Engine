"""
Chunking service - breaks sessions/documents into semantic chunks
"""

import tiktoken
from typing import List, Dict, Any
from datetime import datetime
from ..models import Chunk


class Chunker:
    """Chunk sessions and documents"""
    
    def __init__(self, max_tokens: int = 800, encoding_name: str = "cl100k_base"):
        """
        Initialize chunker
        
        Args:
            max_tokens: Maximum tokens per chunk
            encoding_name: Tokenizer encoding to use
        """
        self.max_tokens = max_tokens
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except:
            # Fallback to approximate tokenization
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Rough approximation: 1 token ≈ 4 characters
            return len(text) // 4
    
    def chunk_session(
        self, 
        messages: List[Dict[str, Any]], 
        session_id: str,
        document_date: datetime
    ) -> List[Chunk]:
        """
        Chunk a chat session into semantic chunks
        
        Args:
            messages: List of messages with 'role' and 'content'
            session_id: Session identifier
            document_date: Timestamp for the session
        
        Returns:
            List of Chunk objects
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        start_idx = 0
        chunk_id = 0
        
        for msg_idx, msg in enumerate(messages):
            content = f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            tokens = self.count_tokens(content)
            
            # Check if adding this message would exceed limit
            if current_tokens + tokens > self.max_tokens and current_chunk:
                # Save current chunk
                chunk_text = "\n".join(current_chunk)
                chunks.append(Chunk(
                    chunk_id=f"{session_id}_chunk_{chunk_id}",
                    session_id=session_id,
                    text=chunk_text,
                    start_idx=start_idx,
                    end_idx=msg_idx - 1,
                    document_date=document_date,
                    tokens=current_tokens
                ))
                
                # Start new chunk
                current_chunk = [content]
                current_tokens = tokens
                start_idx = msg_idx
                chunk_id += 1
            else:
                current_chunk.append(content)
                current_tokens += tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            chunks.append(Chunk(
                chunk_id=f"{session_id}_chunk_{chunk_id}",
                session_id=session_id,
                text=chunk_text,
                start_idx=start_idx,
                end_idx=len(messages) - 1,
                document_date=document_date,
                tokens=current_tokens
            ))
        
        return chunks
    
    def chunk_document(
        self,
        text: str,
        document_id: str,
        document_date: datetime,
        overlap_tokens: int = 50
    ) -> List[Chunk]:
        """
        Chunk a document with sliding window overlap
        
        Args:
            text: Document text
            document_id: Document identifier
            document_date: Document timestamp
            overlap_tokens: Number of tokens to overlap between chunks
        
        Returns:
            List of Chunk objects
        """
        chunks = []
        
        # Split by paragraphs first for semantic boundaries
        paragraphs = text.split('\n\n')
        
        current_chunk = []
        current_tokens = 0
        chunk_id = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            tokens = self.count_tokens(para)
            
            # If single paragraph exceeds max, split it
            if tokens > self.max_tokens:
                # Save current chunk if any
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(Chunk(
                        chunk_id=f"{document_id}_chunk_{chunk_id}",
                        session_id=document_id,
                        text=chunk_text,
                        start_idx=len(chunks),
                        end_idx=len(chunks),
                        document_date=document_date,
                        tokens=current_tokens
                    ))
                    chunk_id += 1
                    current_chunk = []
                    current_tokens = 0
                
                # Split large paragraph by sentences
                sentences = para.split('. ')
                temp_chunk = []
                temp_tokens = 0
                
                for sent in sentences:
                    sent_tokens = self.count_tokens(sent)
                    if temp_tokens + sent_tokens > self.max_tokens and temp_chunk:
                        chunk_text = '. '.join(temp_chunk)
                        chunks.append(Chunk(
                            chunk_id=f"{document_id}_chunk_{chunk_id}",
                            session_id=document_id,
                            text=chunk_text,
                            start_idx=len(chunks),
                            end_idx=len(chunks),
                            document_date=document_date,
                            tokens=temp_tokens
                        ))
                        chunk_id += 1
                        temp_chunk = []
                        temp_tokens = 0
                    
                    temp_chunk.append(sent)
                    temp_tokens += sent_tokens
                
                # Save remaining
                if temp_chunk:
                    chunk_text = '. '.join(temp_chunk)
                    current_chunk = [chunk_text]
                    current_tokens = temp_tokens
            
            # Normal case: add paragraph to chunk
            elif current_tokens + tokens > self.max_tokens and current_chunk:
                # Save current chunk
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(Chunk(
                    chunk_id=f"{document_id}_chunk_{chunk_id}",
                    session_id=document_id,
                    text=chunk_text,
                    start_idx=len(chunks),
                    end_idx=len(chunks),
                    document_date=document_date,
                    tokens=current_tokens
                ))
                chunk_id += 1
                
                # Start new chunk with overlap (last paragraph)
                if overlap_tokens > 0 and current_chunk:
                    current_chunk = [current_chunk[-1], para]
                    current_tokens = self.count_tokens(current_chunk[-2]) + tokens
                else:
                    current_chunk = [para]
                    current_tokens = tokens
            else:
                current_chunk.append(para)
                current_tokens += tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(Chunk(
                chunk_id=f"{document_id}_chunk_{chunk_id}",
                session_id=document_id,
                text=chunk_text,
                start_idx=len(chunks),
                end_idx=len(chunks),
                document_date=document_date,
                tokens=current_tokens
            ))
        
        return chunks
