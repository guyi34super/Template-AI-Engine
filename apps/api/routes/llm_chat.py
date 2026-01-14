"""
LLM Chat API endpoint for conversational AI and data manipulation.
Integrates Phi-3 model for intelligent document processing.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from core.llm import Phi3LLM

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm", tags=["LLM"])

# Initialize LLM (singleton pattern)
_llm_instance: Optional[Phi3LLM] = None


def get_llm() -> Phi3LLM:
    """Get or create LLM instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = Phi3LLM()
    return _llm_instance


# Request/Response Models
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")


class ChatResponse(BaseModel):
    response: str = Field(..., description="AI response")
    model: str = Field(default="Phi-3-mini-4k-instruct", description="Model used")


class ExtractRequest(BaseModel):
    text: str = Field(..., description="Text to extract data from")
    fields: List[str] = Field(..., description="Fields to extract")


class ExtractResponse(BaseModel):
    data: Dict[str, str] = Field(..., description="Extracted structured data")


class OCRCorrectionRequest(BaseModel):
    text: str = Field(..., description="OCR text to correct")


class OCRCorrectionResponse(BaseModel):
    corrected_text: str = Field(..., description="Corrected text")


class SummarizeRequest(BaseModel):
    text: str = Field(..., description="Text to summarize")
    max_length: int = Field(200, ge=50, le=1000, description="Maximum summary length in words")


class SummarizeResponse(BaseModel):
    summary: str = Field(..., description="Document summary")


class ClassifyRequest(BaseModel):
    text: str = Field(..., description="Text to classify")
    categories: List[str] = Field(..., description="Possible categories")


class ClassifyResponse(BaseModel):
    category: str = Field(..., description="Predicted category")


class QARequest(BaseModel):
    question: str = Field(..., description="Question to answer")
    context: str = Field(..., description="Context for answering")


class QAResponse(BaseModel):
    answer: str = Field(..., description="Answer to the question")


# API Endpoints
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the AI assistant.
    
    Use this endpoint for conversational AI interactions.
    """
    try:
        llm = get_llm()
        response = llm.chat(
            user_message=request.message,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens
        )
        
        return ChatResponse(response=response)
        
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract", response_model=ExtractResponse)
async def extract_structured_data(request: ExtractRequest):
    """
    Extract structured data from unstructured text.
    
    Useful for parsing forms, documents, and extracting specific fields.
    """
    try:
        llm = get_llm()
        extracted_data = llm.extract_structured_data(
            text=request.text,
            fields=request.fields
        )
        
        return ExtractResponse(data=extracted_data)
        
    except Exception as e:
        logger.error(f"Data extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correct-ocr", response_model=OCRCorrectionResponse)
async def correct_ocr(request: OCRCorrectionRequest):
    """
    Correct OCR errors using AI.
    
    Improves accuracy of text extracted from images/PDFs.
    """
    try:
        llm = get_llm()
        corrected = llm.correct_ocr_text(request.text)
        
        return OCRCorrectionResponse(corrected_text=corrected)
        
    except Exception as e:
        logger.error(f"OCR correction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_document(request: SummarizeRequest):
    """
    Summarize a document.
    
    Generates concise summaries of long documents.
    """
    try:
        llm = get_llm()
        summary = llm.summarize_document(
            text=request.text,
            max_length=request.max_length
        )
        
        return SummarizeResponse(summary=summary)
        
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify", response_model=ClassifyResponse)
async def classify_document(request: ClassifyRequest):
    """
    Classify a document into categories.
    
    Useful for automatic document categorization and routing.
    """
    try:
        llm = get_llm()
        category = llm.classify_document(
            text=request.text,
            categories=request.categories
        )
        
        return ClassifyResponse(category=category)
        
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer", response_model=QAResponse)
async def answer_question(request: QARequest):
    """
    Answer a question based on provided context.
    
    Extracts answers from document context using AI.
    """
    try:
        llm = get_llm()
        answer = llm.answer_question(
            question=request.question,
            context=request.context
        )
        
        return QAResponse(answer=answer)
        
    except Exception as e:
        logger.error(f"Question answering failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Check if LLM is loaded and ready."""
    try:
        llm = get_llm()
        return {
            "status": "healthy",
            "model": "Phi-3-mini-4k-instruct",
            "model_loaded": llm.llm is not None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
