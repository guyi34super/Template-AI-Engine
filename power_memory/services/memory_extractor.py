"""
Memory Extractor - extracts atomic memories from chunks using LLM
"""

import json
import uuid
import re
from typing import List, Optional
from datetime import datetime
from ..models import Memory, Chunk, MemoryStatus


class MemoryExtractor:
    """Extract atomic memories from text chunks"""
    
    def __init__(self, llm):
        """Initialize with LLM instance"""
        self.llm = llm
    
    def extract_memories(
        self,
        chunk: Chunk,
        user_id: Optional[str] = None,
        context: Optional[str] = None
    ) -> List[Memory]:
        """
        Extract atomic memories from a chunk
        
        Args:
            chunk: Chunk to extract memories from
            user_id: User identifier for scoping
            context: Additional context for disambiguation
        
        Returns:
            List of Memory objects
        """
        
        system_prompt = """You are a memory extraction system. Extract discrete, atomic facts from the text.

Each memory should be:
1. Atomic (one fact per memory)
2. Disambiguated (replace pronouns with names when clear)
3. Self-contained (understandable without the source)

Output JSON array:
[
  {
    "title": "Short canonicalized fact (5-10 words)",
    "body": "Full sentence describing the fact clearly",
    "event_dates": ["YYYY-MM-DD", ...] (dates when event occurred, empty if not mentioned),
    "tags": ["category1", "category2"],
    "confidence": 0.0-1.0
  }
]

Rules:
- Only extract explicit facts, not assumptions
- Use present tense for current facts, past for historical
- Include temporal context in body if mentioned
- Return empty array [] if no clear facts

Examples:
Input: "John prefers vegan meals and avoids dairy."
Output: [
  {
    "title": "John prefers vegan meals",
    "body": "John prefers vegan meals and avoids dairy products",
    "event_dates": [],
    "tags": ["preference", "food"],
    "confidence": 0.95
  }
]"""
        
        user_message = f"""Extract memories from this text:

Text: {chunk.text}

Document Date: {chunk.document_date.isoformat()}
"""
        
        if context:
            user_message += f"\nContext: {context}"
        
        user_message += "\n\nReturn JSON array of memories:"
        
        try:
            response = self.llm.chat(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=1500,
                temperature=0.0
            )
            
            # Parse JSON response
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if not match:
                return []
            
            memory_data = json.loads(match.group(0))
            
            # Convert to Memory objects
            memories = []
            for mem_dict in memory_data:
                try:
                    memory = Memory(
                        memory_id=str(uuid.uuid4()),
                        title=mem_dict.get('title', ''),
                        body=mem_dict.get('body', ''),
                        document_date=chunk.document_date,
                        event_dates=mem_dict.get('event_dates', []),
                        source_chunk=chunk.chunk_id,
                        status=MemoryStatus.ACTIVE,
                        tags=mem_dict.get('tags', []),
                        confidence=mem_dict.get('confidence', 0.8),
                        user_id=user_id,
                        session_id=chunk.session_id
                    )
                    memories.append(memory)
                except Exception as e:
                    print(f"   ⚠️ Error creating memory: {e}")
                    continue
            
            return memories
            
        except Exception as e:
            print(f"   ❌ Error extracting memories: {e}")
            return []
    
    def extract_temporal_info(self, text: str, document_date: datetime) -> List[str]:
        """
        Extract explicit event dates from text
        
        Args:
            text: Text to analyze
            document_date: Reference date for relative dates
        
        Returns:
            List of ISO date strings
        """
        
        system_prompt = """Extract explicit dates from the text. Convert relative dates to absolute dates.

Return JSON: {"dates": ["YYYY-MM-DD", ...]}

Examples:
- "last Monday" with reference 2025-01-10 -> {"dates": ["2025-01-06"]}
- "on June 15" with reference 2025-01-10 -> {"dates": ["2024-06-15"]}
- "no specific date mentioned" -> {"dates": []}"""
        
        user_message = f"""Text: {text}

Reference date (today): {document_date.strftime('%Y-%m-%d')}

Extract dates as JSON:"""
        
        try:
            response = self.llm.chat(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=300,
                temperature=0.0
            )
            
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data.get('dates', [])
            
            return []
        except:
            return []
