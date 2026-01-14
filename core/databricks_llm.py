"""
Databricks LLM Integration for Document Processing
Uses Databricks serving endpoints (Meta Llama 3.1 8B Instruct) for:
- Data extraction and manipulation
- OCR text correction and structuring
- Structured JSON output generation
"""
import os
import json
import logging
from typing import Dict, Any, Optional
import requests

# Import config to load .env file
from core import config

logger = logging.getLogger(__name__)


class DatabricksLLM:
    """
    Databricks LLM wrapper for document processing tasks.
    Uses Meta Llama 3.1 8B Instruct model via Databricks serving endpoints.
    """
    
    def __init__(self, token: Optional[str] = None, endpoint: Optional[str] = None):
        """
        Initialize Databricks LLM client.
        
        Args:
            token: Databricks API token. If None, reads from DATABRICKS_TOKEN env var.
            endpoint: Full endpoint URL. If None, reads from DATABRICKS_LLM_ENDPOINT env var.
        """
        self.token = token or os.getenv("DATABRICKS_TOKEN")
        self.endpoint = endpoint or os.getenv("DATABRICKS_LLM_ENDPOINT")
        self.supports_json_mode = True  # Flag for JSON mode support
        
        if not self.token:
            raise ValueError("Databricks token not provided. Set DATABRICKS_TOKEN environment variable.")
        
        if not self.endpoint:
            raise ValueError("Databricks endpoint not provided. Set DATABRICKS_LLM_ENDPOINT environment variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        logger.info("✅ Databricks LLM client initialized")
        print("✅ Databricks LLM client initialized")
    
    def chat(self, user_message: str, system_prompt: Optional[str] = None, 
             max_tokens: int = 4096, temperature: float = 0.1, response_format: Optional[Dict] = None) -> str:
        """
        Send a chat request to Databricks LLM endpoint.
        
        Args:
            user_message: User's message/prompt
            system_prompt: Optional system prompt for context
            max_tokens: Maximum tokens to generate (default: 4096)
            temperature: Sampling temperature (default: 0.1 for deterministic output)
            response_format: Optional response format hint (e.g., {"type": "json_object"})
            
        Returns:
            Model's response as string
        """
        if system_prompt is None:
            system_prompt = "You are a helpful AI assistant specialized in data extraction and document processing."
        
        # Construct messages in the format expected by Llama models
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Prepare request payload
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # Add response format if provided (for JSON mode)
        if response_format:
            payload["response_format"] = response_format
        
        try:
            logger.debug(f"Sending request to Databricks endpoint: {self.endpoint}")
            
            # Make API request
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
                timeout=300  # 5 minute timeout for large documents
            )
            
            # Check for errors
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Extract the generated text from the response
            # Databricks endpoint format: {"choices": [{"message": {"content": "..."}}]}
            if "choices" in response_data and len(response_data["choices"]) > 0:
                message_content = response_data["choices"][0].get("message", {}).get("content", "")
                return message_content
            else:
                logger.error(f"Unexpected response format: {response_data}")
                return ""
                
        except requests.exceptions.Timeout:
            logger.error("Request to Databricks endpoint timed out")
            raise Exception("Databricks LLM request timed out after 5 minutes")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from Databricks endpoint: {e}")
            logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            raise Exception(f"Databricks LLM HTTP error: {str(e)}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error to Databricks endpoint: {e}")
            raise Exception(f"Databricks LLM request failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error in Databricks LLM: {e}")
            raise
    
    def chat_batch(self, requests_list: list, max_tokens: int = 4096, temperature: float = 0.1) -> list:
        """
        Send multiple chat requests as a batch to Databricks (if supported).
        Falls back to parallel individual requests if batch API not available.
        
        Args:
            requests_list: List of dicts with 'user_message' and optional 'system_prompt'
            max_tokens: Maximum tokens per response
            temperature: Sampling temperature
            
        Returns:
            List of response strings in same order as requests
        """
        # Try batch format first
        batch_payload = {
            "requests": [
                {
                    "messages": [
                        {"role": "system", "content": req.get("system_prompt", "You are a helpful AI assistant.")},
                        {"role": "user", "content": req["user_message"]}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                for req in requests_list
            ]
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=batch_payload,
                timeout=300
            )
            
            # Check if batch API is supported
            if response.status_code == 200:
                response_data = response.json()
                
                # Extract responses from batch format
                if "responses" in response_data:
                    return [
                        resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                        for resp in response_data["responses"]
                    ]
                elif "choices" in response_data:
                    # Single response format - batch not supported
                    raise ValueError("Batch API not supported")
            else:
                raise ValueError("Batch API not supported")
                
        except Exception as e:
            logger.warning(f"Batch API not available: {e}")
            # Return None to signal batch not supported, let caller handle parallel execution
            return None
    
    def extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from LLM response, handling markdown code blocks.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Parsed JSON as dictionary
        """
        import re
        
        # Clean response - remove markdown code blocks if present
        cleaned = response.strip()
        
        if cleaned.startswith("```"):
            # Remove ```json or ``` blocks
            lines = cleaned.split('\n')
            start_idx = 0
            end_idx = len(lines)
            
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx == 0:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            
            cleaned = '\n'.join(lines[start_idx:end_idx])
        
        # Try to find JSON array in response
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, list):
                    return {"rows": parsed}
                else:
                    return {"rows": [parsed]}
            except json.JSONDecodeError:
                pass
        
        # Try parsing entire cleaned response
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return {"rows": parsed}
            elif isinstance(parsed, dict):
                # If it's already wrapped, check for common keys
                if "rows" in parsed:
                    return parsed
                elif "data" in parsed:
                    data = parsed["data"]
                    return {"rows": data if isinstance(data, list) else [data]}
                else:
                    # Single record
                    return {"rows": [parsed]}
            else:
                return {"rows": [], "error": "Unexpected response format"}
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            # Try to extract any JSON-like structure
            bracket_match = re.search(r'\{[^{}]*\}', cleaned)
            if bracket_match:
                try:
                    parsed = json.loads(bracket_match.group(0))
                    return {"rows": [parsed]}
                except:
                    pass
            
            return {
                "rows": [],
                "raw_response": response[:500],
                "error": f"JSON parse error: {str(e)}"
            }


# Helper function to get LLM instance
def get_llm() -> DatabricksLLM:
    """
    Get configured Databricks LLM instance.
    
    Returns:
        DatabricksLLM instance
    """
    return DatabricksLLM()


if __name__ == "__main__":
    # Test the Databricks LLM client
    print("Testing Databricks LLM client...")
    
    try:
        llm = DatabricksLLM()
        
        # Simple test
        response = llm.chat(
            user_message="What is 2+2? Answer in one sentence.",
            max_tokens=50
        )
        
        print(f"\n✅ Test successful!")
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
