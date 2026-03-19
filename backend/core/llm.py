"""
Phi-3 LLM Integration for Chatbot and Data Manipulation
Uses the downloaded Phi-3-mini model with optimized prompts for:
- Conversational AI (chatbot)
- Data extraction and manipulation
- OCR text correction and structuring
"""
import os
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class Phi3LLM:
    """
    Phi-3 model wrapper for chatbot and data manipulation tasks.
    Uses llama-cpp-python for efficient GGUF model inference on CPU.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize Phi-3 model.
        
        Args:
            model_path: Path to GGUF model file. If None, uses default location.
        """
        if model_path is None:
            # Get project root (two levels up from core/)
            project_root = os.path.dirname(os.path.dirname(__file__))
            model_path = os.path.join(
                project_root,
                "LLM_model", 
                "Phi-3-mini-4k-instruct",
                "Phi-3-mini-4k-instruct-q4.gguf"
            )
        
        self.model_path = model_path
        self.llm = None
        self._load_model()
    
    def _load_model(self):
        """Load the GGUF model using llama-cpp-python."""
        try:
            from llama_cpp import Llama
            
            print(f"📥 Loading Phi-3 model from: {self.model_path}")
            
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=8192,  # Context window (increased for large documents)
                n_threads=4,  # CPU threads
                n_gpu_layers=0,  # CPU only
                verbose=False
            )
            
            print("✅ Phi-3 model loaded successfully!")
            logger.info("Phi-3 model initialized")
            
        except ImportError:
            print("❌ llama-cpp-python not installed")
            print("📦 Installing: pip install llama-cpp-python")
            import subprocess
            subprocess.run([
                "pip", "install", "llama-cpp-python", "--quiet"
            ])
            # Retry after installation
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                n_threads=4,
                n_gpu_layers=0,
                verbose=False
            )
            print("✅ Phi-3 model loaded successfully!")
            
        except Exception as e:
            logger.error(f"Failed to load Phi-3 model: {e}")
            raise
    
    def chat(self, user_message: str, system_prompt: Optional[str] = None, 
             max_tokens: int = 512) -> str:
        """
        Chat with the model.
        
        Args:
            user_message: User's message
            system_prompt: Optional system prompt for context
            max_tokens: Maximum tokens to generate
            
        Returns:
            Model's response
        """
        if system_prompt is None:
            system_prompt = "You are a helpful AI assistant specialized in data analysis and document processing."
        
        # Phi-3 chat template
        prompt = f"<|system|>\n{system_prompt}<|end|>\n<|user|>\n{user_message}<|end|>\n<|assistant|>\n"
        
        try:
            response = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
                stop=["<|end|>", "<|user|>"],
                echo=False
            )
            
            return response['choices'][0]['text'].strip()
            
        except Exception as e:
            logger.error(f"Chat generation failed: {e}")
            return f"Error: {e}"
    
    def extract_structured_data(self, text: str, fields: List[str]) -> Dict[str, str]:
        """
        Extract structured data from unstructured text.
        
        Args:
            text: Input text to process
            fields: List of field names to extract
            
        Returns:
            Dictionary with extracted field values
        """
        fields_str = ", ".join(fields)
        
        system_prompt = """You are a data extraction expert. Extract information accurately and return it in JSON format."""
        
        user_message = f"""Extract the following fields from this text:
Fields: {fields_str}

Text:
{text}

Return the data as JSON with keys: {fields_str}
If a field is not found, use "N/A" as the value."""
        
        response = self.chat(user_message, system_prompt, max_tokens=1024)
        
        # Try to parse JSON response
        try:
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                # Fallback: parse line by line
                result = {}
                for field in fields:
                    pattern = rf'{field}[:\s]+([^\n]+)'
                    match = re.search(pattern, response, re.IGNORECASE)
                    result[field] = match.group(1).strip() if match else "N/A"
                return result
                
        except Exception as e:
            logger.warning(f"JSON parsing failed: {e}")
            return {field: "N/A" for field in fields}
    
    def correct_ocr_text(self, ocr_text: str) -> str:
        """
        Correct OCR errors using LLM.
        
        Args:
            ocr_text: Text from OCR with potential errors
            
        Returns:
            Corrected text
        """
        system_prompt = """You are an OCR correction expert. Fix spelling errors, formatting issues, and recognize proper names, numbers, and dates. Preserve the original structure."""
        
        user_message = f"""Correct any OCR errors in this text while preserving the structure:

{ocr_text}

Return only the corrected text."""
        
        return self.chat(user_message, system_prompt, max_tokens=2048)
    
    def summarize_document(self, text: str, max_length: int = 200) -> str:
        """
        Summarize a document.
        
        Args:
            text: Document text
            max_length: Maximum summary length in words
            
        Returns:
            Summary text
        """
        system_prompt = "You are a document summarization expert. Create concise, accurate summaries."
        
        user_message = f"""Summarize this document in {max_length} words or less:

{text}"""
        
        return self.chat(user_message, system_prompt, max_tokens=512)
    
    def classify_document(self, text: str, categories: List[str]) -> str:
        """
        Classify a document into categories.
        
        Args:
            text: Document text
            categories: List of possible categories
            
        Returns:
            Most likely category
        """
        categories_str = ", ".join(categories)
        
        system_prompt = "You are a document classification expert. Classify documents accurately."
        
        user_message = f"""Classify this document into one of these categories: {categories_str}

Document:
{text[:1000]}

Return only the category name."""
        
        response = self.chat(user_message, system_prompt, max_tokens=50)
        
        # Find matching category
        response_lower = response.lower()
        for category in categories:
            if category.lower() in response_lower:
                return category
        
        return categories[0]  # Default to first category
    
    def answer_question(self, question: str, context: str) -> str:
        """
        Answer a question based on context.
        
        Args:
            question: Question to answer
            context: Context containing the answer
            
        Returns:
            Answer text
        """
        system_prompt = "You are a question-answering expert. Answer questions accurately based on the provided context."
        
        user_message = f"""Context:
{context}

Question: {question}

Answer:"""
        
        return self.chat(user_message, system_prompt, max_tokens=512)


# Example usage
if __name__ == "__main__":
    print("🤖 Initializing Phi-3 LLM...")
    llm = Phi3LLM()
    
    # Test chatbot
    print("\n" + "="*60)
    print("💬 Chatbot Test")
    print("="*60)
    response = llm.chat("What can you help me with?")
    print(f"Assistant: {response}")
    
    # Test data extraction
    print("\n" + "="*60)
    print("📊 Data Extraction Test")
    print("="*60)
    sample_text = """
    Employee Name: John Smith
    Employee ID: EMP-12345
    Department: Engineering
    Salary: $85,000
    Start Date: 2023-01-15
    """
    
    fields = ["Employee Name", "Employee ID", "Department", "Salary", "Start Date"]
    extracted = llm.extract_structured_data(sample_text, fields)
    print("Extracted Data:")
    for key, value in extracted.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Tests complete!")
