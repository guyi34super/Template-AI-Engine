"""
Databricks Embeddings Integration
Uses Databricks serving endpoints (gte-large-en) for text embeddings
"""
import os
import logging
from typing import List
import requests

logger = logging.getLogger(__name__)


class DatabricksEmbeddings:
    """Databricks embeddings using gte-large-en model"""
    
    def __init__(self, token: str = None, endpoint: str = None):
        self.token = token or os.getenv("DATABRICKS_TOKEN")
        
        # Construct full endpoint URL
        if endpoint:
            self.endpoint = endpoint
        else:
            # Get base URL from LLM endpoint
            llm_endpoint = os.getenv("DATABRICKS_LLM_ENDPOINT", "")
            if llm_endpoint:
                # Extract base URL: https://adb-xxx.azuredatabricks.net/serving-endpoints/
                base_url = llm_endpoint.rsplit("/", 2)[0]
                embedding_model = os.getenv("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")
                self.endpoint = f"{base_url}/{embedding_model}/invocations"
            else:
                raise ValueError("DATABRICKS_LLM_ENDPOINT not set")
        
        if not self.token:
            raise ValueError("DATABRICKS_TOKEN not set")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"✅ Databricks Embeddings initialized: {self.endpoint}")
    
    def embed_texts(self, texts: List[str], timeout: int = 10) -> List[List[float]]:
        """Create embeddings for a list of texts with configurable timeout"""
        if not texts:
            return []
        
        try:
            # Databricks embedding format
            payload = {"input": texts}
            
            logger.info(f"Sending {len(texts)} texts to embedding endpoint (timeout={timeout}s)")
            
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
                timeout=timeout  # Configurable timeout
            )
            
            logger.info(f"Embedding response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            
            # Extract embeddings from response
            if "data" in data:
                embeddings = [item["embedding"] for item in data["data"]]
                logger.info(f"Successfully created {len(embeddings)} embeddings")
                return embeddings
            else:
                logger.error(f"Unexpected embedding response format: {data}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error(f"Embedding request timed out after 30s")
            raise Exception("Embedding timeout")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from embedding endpoint: {e}")
            logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            raise
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise


# Global singleton
_embeddings_instance = None


def get_embeddings_instance():
    """Get singleton embeddings instance"""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = DatabricksEmbeddings()
    return _embeddings_instance
