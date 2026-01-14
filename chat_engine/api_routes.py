"""
Chat API Routes for JSON modification
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import os
from pathlib import Path

# Import chat engine components
import sys
sys.path.append(str(Path(__file__).parent.parent))
from chat_engine.chat_handler import ChatHandler
from core.databricks_llm import DatabricksLLM

router = APIRouter(prefix="/chat", tags=["Chat Engine"])


class ChatModifyRequest(BaseModel):
    """Request model for chat-based JSON modification"""
    data: List[Dict[str, Any]] = Field(
        ...,
        description="Array of JSON records to modify",
        example=[
            {"employee": "John Doe", "hours": 40, "rate": 25.00},
            {"employee": "Jane Smith", "hours": 35, "rate": 30.00}
        ]
    )
    query: str = Field(
        ...,
        description="Natural language query describing the modification",
        example="Increase hours by 10% for all employees"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {"employee": "John Doe", "hours": 40, "rate": 25.00},
                    {"employee": "Jane Smith", "hours": 35, "rate": 30.00}
                ],
                "query": "Increase hours by 10% for all employees"
            }
        }


class ChatModifyFileRequest(BaseModel):
    """Request model for file-based chat modification"""
    file_path: str = Field(
        ...,
        description="Path to the JSON or JSONL file to modify",
        example="output/extract/JasperReport_20260113_105756.jsonl"
    )
    query: str = Field(
        ...,
        description="Natural language query describing the modification",
        example="Change all 'Regular' earning codes to 'Overtime'"
    )
    output_file: Optional[str] = Field(
        None,
        description="Optional output file path (defaults to _modified suffix)",
        example="output/extract/modified_data.jsonl"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "output/extract/JasperReport_20260113_105756.jsonl",
                "query": "Change all 'Regular' earning codes to 'Overtime'",
                "output_file": "output/extract/modified_data.jsonl"
            }
        }


@router.post(
    "/modify",
    summary="Modify JSON data with query",
    description="Modify JSON records using natural language query. Supports filtering and transformation.",
    response_description="Returns modified records with change summary"
)
async def modify_json(request: ChatModifyRequest):
    """
    Modify JSON data based on natural language query.
    
    **Features:**
    - Hash-protected modifications for data integrity
    - LLM-powered query understanding
    - Change verification and tracking
    - Supports filtering, updating, and transforming records
    
    **Example queries:**
    - "Increase hours by 10% for all employees"
    - "Change all Regular earning codes to Overtime"
    - "Set rate to 35.00 for employees with more than 40 hours"
    - "Remove all records where status is 'inactive'"
    
    **Returns:**
    - success: Operation status
    - changes_summary: Description of modifications made
    - modified_data: Complete modified dataset
    """
    try:
        # Initialize LLM
        llm_endpoint = os.getenv("DATABRICKS_LLM_ENDPOINT")
        token = os.getenv("DATABRICKS_TOKEN")
        
        if not llm_endpoint or not token:
            raise HTTPException(
                status_code=500,
                detail="LLM endpoint or token not configured"
            )
        
        llm = DatabricksLLM(endpoint=llm_endpoint, token=token)
        handler = ChatHandler(llm)
        
        # Process query
        result = handler.process_query(request.data, request.query)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Modification failed'))
        
        return {
            "success": True,
            "changes_summary": result['changes_summary'],
            "modified_data": result['modified_data']
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/modify-file",
    summary="Modify JSON/JSONL file with query",
    description="Load, modify, and save JSON/JSONL files using natural language queries.",
    response_description="Returns modification summary and output file path"
)
async def modify_file(request: ChatModifyFileRequest):
    """
    Modify JSON/JSONL file based on natural language query.
    
    **Supported Formats:**
    - JSON (.json) - Array of objects
    - JSONL (.jsonl) - One JSON object per line
    
    **Workflow:**
    1. Load data from file
    2. Filter relevant records based on query
    3. Add hash protection
    4. Send to LLM for modification
    5. Verify changes against hashes
    6. Merge changes back
    7. Save to output file
    
    **Example:**
    ```json
    {
        "file_path": "output/extract/JasperReport_20260113_105756.jsonl",
        "query": "Change all 'Regular' earning codes to 'Overtime'",
        "output_file": "output/extract/modified_data.jsonl"
    }
    ```
    
    **Returns:**
    - success: Operation status
    - input_file: Original file path
    - output_file: Modified file path
    - changes_summary: Description of modifications
    - total_records: Number of records processed
    """
    try:
        # Initialize LLM
        llm_endpoint = os.getenv("DATABRICKS_LLM_ENDPOINT")
        token = os.getenv("DATABRICKS_TOKEN")
        
        if not llm_endpoint or not token:
            raise HTTPException(
                status_code=500,
                detail="LLM endpoint or token not configured"
            )
        
        llm = DatabricksLLM(endpoint=llm_endpoint, token=token)
        handler = ChatHandler(llm)
        
        # Check if file exists
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
        
        # Process query
        result = handler.process_from_file(
            input_file=request.file_path,
            query=request.query,
            output_file=request.output_file
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Modification failed'))
        
        return {
            "success": True,
            "input_file": request.file_path,
            "output_file": request.output_file,
            "changes_summary": result['changes_summary'],
            "total_records": len(result['modified_data'])
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upload-and-modify",
    summary="Upload and modify JSON/JSONL file",
    description="Upload a JSON/JSONL file and modify it in one step using a natural language query.",
    response_description="Returns modification summary and download link"
)
async def upload_and_modify(
    file: UploadFile = File(..., description="JSON or JSONL file to upload and modify"),
    query: str = Form(
        ...,
        description="Natural language query describing the modification",
        example="Increase hours by 10% for all employees"
    )
):
    """
    Upload JSON/JSONL file and modify based on query.
    
    **Perfect for:**
    - Quick modifications without pre-existing files
    - Testing chat modifications
    - One-off data transformations
    
    **How to use:**
    1. Click "Try it out"
    2. Click "Choose File" and select your JSON/JSONL file
    3. Enter your query (e.g., "Change all Regular to Overtime")
    4. Click "Execute"
    5. Download modified file using the download_url
    
    **Supported file formats:**
    - .json (array of JSON objects)
    - .jsonl (one JSON object per line)
    
    **Example queries:**
    - "Increase all rates by 5%"
    - "Set status to 'approved' for all records"
    - "Change department 'Sales' to 'Revenue'"
    - "Add a new field 'processed' with value true"
    
    **Returns:**
    - success: Operation status
    - original_file: Uploaded filename
    - output_file: Modified file path
    - changes_summary: Description of changes
    - total_records: Number of records processed
    - download_url: Endpoint to download modified file
    """
    try:
        # Save uploaded file
        upload_dir = Path("output/chat/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        temp_path = upload_dir / file.filename
        with open(temp_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Initialize LLM
        llm_endpoint = os.getenv("DATABRICKS_LLM_ENDPOINT")
        token = os.getenv("DATABRICKS_TOKEN")
        
        if not llm_endpoint or not token:
            raise HTTPException(
                status_code=500,
                detail="LLM endpoint or token not configured"
            )
        
        llm = DatabricksLLM(endpoint=llm_endpoint, token=token)
        handler = ChatHandler(llm)
        
        # Load data for PowerMemory analysis
        is_jsonl = file.filename.endswith('.jsonl')
        if is_jsonl:
            with open(temp_path, 'r', encoding='utf-8') as f:
                json_data = [json.loads(line.strip()) for line in f if line.strip()]
        else:
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'rows' in data:
                    json_data = data['rows']
                elif isinstance(data, list):
                    json_data = data
                else:
                    json_data = [data]
        
        # Use PowerMemory for file structure intelligence (GLOBAL CACHE)
        try:
            from api_server import power_memory
            if power_memory and len(json_data) > 0:
                print(f"\n📊 Analyzing file structure (Global Cache)...")
                # Analyze file structure with global cache
                cache = power_memory.analyze_file(
                    data=json_data,
                    file_path=str(temp_path),
                    user_id="global"  # Global cache across all users
                )
                
                # Get manipulation strategy for known structures
                if cache.usage_count > 1:
                    print(f"   🚀 Fast path: Structure seen in {len(cache.file_paths)} files")
                    strategy = power_memory.get_manipulation_strategy(cache, query)
                    print(f"   💡 Strategy: {strategy.get('strategy', 'Standard manipulation')}")
                else:
                    print(f"   📦 New structure - will be cached for future uploads")
        except Exception as e:
            print(f"   ⚠️ PowerMemory integration skipped: {e}")
        
        # Generate output filename
        output_dir = Path("output/chat/modified")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"modified_{file.filename}"
        
        # Process query
        result = handler.process_from_file(
            input_file=str(temp_path),
            query=query,
            output_file=str(output_file)
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Modification failed'))
        
        return {
            "success": True,
            "original_file": file.filename,
            "output_file": str(output_file),
            "changes_summary": result['changes_summary'],
            "total_records": len(result['modified_data']),
            "download_url": f"/chat/download/{output_file.name}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()


@router.get(
    "/download/{filename}",
    summary="Download modified file",
    description="Download a previously modified JSON/JSONL file.",
    response_description="Returns the file for download"
)
async def download_modified(filename: str):
    """
    Download modified file from the chat engine.
    
    **Usage:**
    - After using /upload-and-modify, use the download_url returned
    - Or directly access /chat/download/{filename}
    
    **Location:**
    Files are stored in: `output/chat/modified/`
    
    **Example:**
    ```
    GET /chat/download/modified_data.jsonl
    ```
    """
    from fastapi.responses import FileResponse
    
    file_path = Path(f"output/chat/modified/{filename}")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/json'
    )
