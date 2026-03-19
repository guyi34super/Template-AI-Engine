"""
API routes for Mapping Engine
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import Dict, List, Optional, Any
import json
from pathlib import Path
from pydantic import BaseModel

from .engine import MappingEngine
from .models import MappingConfig, MappingResult, TransformedData, MappingStrategy

router = APIRouter(prefix="/mapping", tags=["Mapping Engine"])


# Request/Response Models
class MapFieldsRequest(BaseModel):
    source_json: Dict[str, Any] | List[Dict[str, Any]]
    target_schema: Dict[str, Any] | List[str]
    config: Optional[MappingConfig] = None


class TransformDataRequest(BaseModel):
    source_data: List[Dict[str, Any]]
    mapping_result: MappingResult
    fill_unmapped: bool = False


class QuickMapRequest(BaseModel):
    source_fields: List[str]
    target_fields: List[str]
    manual_overrides: Optional[Dict[str, str]] = None


# Global mapping engine instance
mapping_engine: Optional[MappingEngine] = None


def get_mapping_engine():
    """Get or initialize mapping engine"""
    global mapping_engine
    if mapping_engine is None:
        from core.llm import get_llm_instance
        llm = get_llm_instance()
        mapping_engine = MappingEngine(llm=llm)
    return mapping_engine


@router.post(
    "/map-fields",
    response_model=MappingResult,
    summary="Map JSON Fields",
    description="Intelligently map fields from source JSON to target schema using LLM",
    response_description="Mapping result with field mappings and confidence scores"
)
async def map_fields(request: MapFieldsRequest):
    """
    ## Map Fields from Source JSON to Target Schema
    
    Uses LLM to intelligently map source field names to target schema fields.
    
    **Strategies:**
    - `auto`: LLM-based intelligent mapping
    - `manual`: User-defined mappings only
    - `hybrid`: Manual overrides + LLM for remaining fields
    
    **Example Request:**
    ```json
    {
        "source_json": [{"first_name": "John", "email_address": "john@example.com"}],
        "target_schema": ["FirstName", "Email", "Phone"],
        "config": {
            "strategy": "auto",
            "manual_overrides": {"first_name": "FirstName"}
        }
    }
    ```
    
    **Returns:** MappingResult with field mappings, confidence scores, and unmapped fields
    """
    engine = get_mapping_engine()
    
    result = engine.map_json_fields(
        source_json=request.source_json,
        target_schema=request.target_schema,
        config=request.config
    )
    
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result


@router.post(
    "/map-files",
    summary="Map Fields from Uploaded Files",
    description="Upload source JSON and schema JSON files to get intelligent field mappings",
    response_description="MappingResult with field mappings between uploaded files"
)
async def map_files(
    source_file: UploadFile = File(..., description="Source JSON file with data to map"),
    schema_file: UploadFile = File(..., description="Target schema JSON file"),
    strategy: MappingStrategy = MappingStrategy.AUTO,
    manual_overrides: Optional[str] = None
):
    """
    ## Map Fields from Uploaded Files
    
    Upload two JSON files:
    - **source_file**: The data file you want to map (e.g., uploaded CSV converted to JSON)
    - **schema_file**: The target schema/template file
    
    **Returns:** Field mappings with confidence scores
    """
    engine = get_mapping_engine()
    
    try:
        # Read source file
        source_content = await source_file.read()
        source_json = json.loads(source_content)
        
        # Read schema file
        schema_content = await schema_file.read()
        target_schema = json.loads(schema_content)
        
        # Parse manual overrides
        overrides = {}
        if manual_overrides:
            overrides = json.loads(manual_overrides)
        
        # Create config
        config = MappingConfig(
            strategy=strategy,
            manual_overrides=overrides
        )
        
        # Map fields
        result = engine.map_json_fields(
            source_json=source_json,
            target_schema=target_schema,
            config=config
        )
        
        if result.error:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/transform",
    response_model=TransformedData,
    summary="Transform Data with Mappings",
    description="Apply field mappings to transform source data to target schema format",
    response_description="TransformedData with original and transformed records"
)
async def transform_data(request: TransformDataRequest):
    """
    ## Transform Data Using Field Mappings
    
    Takes source data and a MappingResult, then transforms all records according to the field mappings.
    
    **Use Case:** After getting mappings from `/map-fields`, use this to transform your actual data.
    
    **Example:**
    ```json
    {
        "source_data": [{"first_name": "John", "email_address": "john@example.com"}],
        "mapping_result": { ... mapping result from /map-fields ... },
        "fill_unmapped": false
    }
    ```
    """
    engine = get_mapping_engine()
    
    result = engine.transform_data(
        source_data=request.source_data,
        mapping_result=request.mapping_result,
        fill_unmapped=request.fill_unmapped
    )
    
    return result


@router.post(
    "/quick-map",
    summary="Quick Field Mapping",
    description="Fast field mapping using just field name lists (no data required)",
    response_description="MappingResult with field mappings"
)
async def quick_map(request: QuickMapRequest):
    """
    ## Quick Field Mapping (Field Names Only)
    
    Fastest way to map fields - just provide lists of field names.
    
    **Perfect for:**
    - Previewing mappings before uploading data
    - Testing mapping strategies
    - Getting quick mapping suggestions
    
    **Example:**
    ```json
    {
        "source_fields": ["first_name", "email_address", "phone_number"],
        "target_fields": ["FirstName", "Email", "Phone", "Address"],
        "manual_overrides": {"first_name": "FirstName"}
    }
    ```
    """
    engine = get_mapping_engine()
    
    # Create dummy JSON objects with field names
    source_json = {field: f"sample_{field}" for field in request.source_fields}
    target_schema = request.target_fields
    
    config = MappingConfig(
        strategy=MappingStrategy.HYBRID if request.manual_overrides else MappingStrategy.AUTO,
        manual_overrides=request.manual_overrides or {}
    )
    
    result = engine.map_json_fields(
        source_json=source_json,
        target_schema=target_schema,
        config=config
    )
    
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result


@router.post(
    "/map-and-transform",
    summary="Map and Transform in One Step",
    description="Upload files, get field mappings AND transformed data in a single operation",
    response_description="TransformedData with mappings and transformed records"
)
async def map_and_transform(
    source_file: UploadFile = File(..., description="Source data file to map and transform"),
    schema_file: UploadFile = File(..., description="Target schema file"),
    strategy: MappingStrategy = MappingStrategy.AUTO,
    fill_unmapped: bool = False
):
    """
    ## One-Step Mapping and Transformation
    
    **Most convenient endpoint** - Upload your files and get transformed data immediately!
    
    This endpoint:
    1. Maps fields from source to target schema
    2. Applies mappings to transform all records
    3. Returns both mapping details and transformed data
    
    **Perfect for:** Complete data transformation workflows
    """
    engine = get_mapping_engine()
    
    try:
        # Read files
        source_content = await source_file.read()
        source_json = json.loads(source_content)
        
        schema_content = await schema_file.read()
        target_schema = json.loads(schema_content)
        
        # Map fields
        config = MappingConfig(strategy=strategy)
        mapping_result = engine.map_json_fields(
            source_json=source_json,
            target_schema=target_schema,
            config=config
        )
        
        if mapping_result.error:
            raise HTTPException(status_code=400, detail=mapping_result.error)
        
        # Transform data
        transformed = engine.transform_data(
            source_data=source_json if isinstance(source_json, list) else [source_json],
            mapping_result=mapping_result,
            fill_unmapped=fill_unmapped
        )
        
        return transformed
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    summary="Mapping Engine Health Check",
    description="Check if mapping engine is initialized and LLM is available"
)
async def health_check():
    """
    ## Health Check
    
    Verify that the Mapping Engine is properly initialized and ready to process requests.
    
    **Returns:**
    - `status`: "healthy" if operational
    - `engine_initialized`: Whether MappingEngine is initialized
    - `llm_available`: Whether LLM is available for intelligent mapping
    """
    engine = get_mapping_engine()
    return {
        "status": "healthy",
        "engine_initialized": engine is not None,
        "llm_available": engine.llm is not None if engine else False
    }


@router.post(
    "/upload-and-map",
    summary="Upload Two JSON Files and Get Mapped Output",
    description="Upload source and target JSON files, map them, and save the result"
)
async def upload_and_map(
    source_file: UploadFile = File(..., description="Source JSON file to map"),
    target_file: UploadFile = File(..., description="Target JSON file (schema or data)"),
    strategy: MappingStrategy = MappingStrategy.AUTO,
    save_output: bool = True
):
    """
    ## Upload and Map Two JSON Files
    
    Upload two JSON files, perform intelligent field mapping, transform the data,
    and optionally save the mapped output to output/mapping directory.
    
    **Returns:**
    - Transformed data with mappings
    - File path where output is saved (if save_output=True)
    """
    engine = get_mapping_engine()
    
    try:
        # Read source file
        source_content = await source_file.read()
        source_json = json.loads(source_content)
        
        # Read target file
        target_content = await target_file.read()
        target_json = json.loads(target_content)
        
        # Map fields
        config = MappingConfig(strategy=strategy)
        mapping_result = engine.map_json_fields(
            source_json=source_json,
            target_schema=target_json,
            config=config
        )
        
        if mapping_result.error:
            raise HTTPException(status_code=400, detail=mapping_result.error)
        
        # Transform data
        transformed = engine.transform_data(
            source_data=source_json if isinstance(source_json, list) else [source_json],
            mapping_result=mapping_result,
            fill_unmapped=False
        )
        
        # Save output if requested
        output_path = None
        if save_output:
            from datetime import datetime
            from pathlib import Path
            
            # Create output directory if not exists
            output_dir = Path("output/mapping")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_name = Path(source_file.filename).stem
            output_filename = f"mapped_{source_name}_{timestamp}.json"
            output_path = output_dir / output_filename
            
            # Save transformed data
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "mapping_info": {
                        "source_file": source_file.filename,
                        "target_file": target_file.filename,
                        "strategy": strategy.value,
                        "total_fields_mapped": mapping_result.total_fields_mapped,
                        "confidence_score": mapping_result.confidence_score,
                        "timestamp": timestamp
                    },
                    "field_mappings": [
                        {
                            "source": m.source_field,
                            "target": m.target_field,
                            "confidence": m.confidence
                        }
                        for m in mapping_result.mappings
                    ],
                    "transformed_data": transformed.transformed_data
                }, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "mapping_result": mapping_result,
            "transformed_data": transformed.transformed_data,
            "output_path": str(output_path) if output_path else None,
            "records_processed": transformed.records_processed,
            "records_failed": transformed.records_failed
        }
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
