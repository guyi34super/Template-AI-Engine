#!/usr/bin/env python3
"""
Direct CSV/Excel to JSON Extraction using Databricks LLM

Clean workflow:
1. Read CSV/Excel file
2. Send to Databricks LLM for extraction
3. Save structured JSON output

Usage:
    python direct_extract.py --input ../files/test2_data.csv
    python direct_extract.py --input ../files/ --pattern "*.csv"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.databricks_llm import DatabricksLLM
from extractors.csv import extract_csv
from extractors.xlsx import extract_xlsx
from extractors.docx import extract_docx
from extractors.txt import extract_txt

try:
    from extractors.easyocr.easyocr_extractor import EasyOCRExtractor
except ImportError:
    EasyOCRExtractor = None


def ensure_output_dirs():
    """Create clean output directory structure"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Create organized subdirectories
    (output_dir / "json").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)
    
    return output_dir


def extract_file(file_path: Path) -> str:
    """
    Extract text from file using appropriate extractor (EasyOCR/Docling for PDFs, native for CSV/Excel)
    
    Args:
        file_path: Path to input file
        
    Returns:
        Extracted text content
    """
    ext = file_path.suffix.lower()
    
    # Use extractors based on file type
    if ext == '.csv':
        result = extract_csv(str(file_path))
        # Convert table blocks to text format
        if result.get('table_blocks'):
            table = result['table_blocks'][0]
            headers = table['headers']
            rows = table['rows']
            lines = [' | '.join(headers)]
            for row in rows:
                lines.append(' | '.join(str(cell) for cell in row))
            return '\n'.join(lines)
        return ''
    
    elif ext in ['.xlsx', '.xls']:
        result = extract_xlsx(str(file_path))
        if result.get('table_blocks'):
            table = result['table_blocks'][0]
            headers = table['headers']
            rows = table['rows']
            lines = [' | '.join(headers)]
            for row in rows:
                lines.append(' | '.join(str(cell) for cell in row))
            return '\n'.join(lines)
        return ''
    
    elif ext == '.txt':
        result = extract_txt(str(file_path))
        text_blocks = result.get('text_blocks', [])
        return '\n'.join(block.get('text', '') for block in text_blocks)
    
    elif ext == '.docx':
        result = extract_docx(str(file_path))
        text_blocks = result.get('text_blocks', [])
        return '\n'.join(block.get('text', '') for block in text_blocks)
    
    elif ext == '.pdf':
        # Use EasyOCR for PDFs
        if EasyOCRExtractor:
            try:
                ocr = EasyOCRExtractor(languages=['en'], gpu=False)
                result = ocr.extract_pdf(str(file_path))
                return result.get('full_text', '')
            except Exception as e:
                print(f"  ⚠️ EasyOCR failed: {e}, trying basic read")
        # Fallback: try to read as text
        return file_path.read_text(encoding='utf-8', errors='ignore')
    
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def build_extraction_prompt() -> str:
    """Build concise system prompt for data extraction"""
    return """You are a Data Extraction Assistant. Extract ALL rows from the data.

## RULES
1. Extract EVERY row - no skipping
2. Normalize: Dates→YYYY-MM-DD, 'nan'→empty string ""
3. Field names: snake_case (first_name, birth_date)
4. employee_number: Use actual value if present, otherwise ""
5. DO NOT copy header names as values

## OUTPUT
Return JSON array of all records:
[
  {"employee_number": "", "first_name": "John", "last_name": "Doe", ...},
  {"employee_number": "", "first_name": "Jane", "last_name": "Smith", ...}
]"""


def extract_with_llm(file_content: str, template_name: str = "Employee_Profile") -> Dict:
    """
    Send data to Databricks LLM for extraction
    
    Args:
        file_content: String content of the file
        template_name: Name of the template to use
        
    Returns:
        Extracted data as dictionary
    """
    llm = DatabricksLLM()
    
    system_prompt = build_extraction_prompt()
    user_message = f"""## DATA TO EXTRACT
```
{file_content}
```

Extract ALL rows. Convert 'nan' to empty string. Use snake_case field names.
Template: {template_name}"""
    
    print("  📤 Sending to Databricks LLM...")
    print(f"  📊 Data size: {len(file_content)} characters")
    
    response = llm.chat(
        user_message=user_message,
        system_prompt=system_prompt,
        max_tokens=8192,
        temperature=0.05
    )
    
    # Parse JSON response
    try:
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith("Here is") or cleaned.startswith("Here's"):
            # Skip intro text
            lines = cleaned.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('```'):
                    cleaned = '\n'.join(lines[i:])
                    break
        
        if cleaned.startswith("```"):
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
        
        cleaned = cleaned.strip()
        data = json.loads(cleaned)
        
        # Handle different response formats
        if isinstance(data, list):
            return {"rows": data}
        elif isinstance(data, dict) and "detectedTemplates" in data:
            # Extract first template
            first_template = list(data["detectedTemplates"].values())[0]
            return {"rows": first_template.get("data", [])}
        elif isinstance(data, dict) and "data" in data:
            return data
        else:
            return {"rows": [data] if isinstance(data, dict) else data}
            
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parsing failed: {e}")
        print(f"  Response preview: {response[:200]}...")
        # Return raw response in error format
        return {
            "error": "JSON parsing failed",
            "raw_response": response[:500],
            "rows": []
        }


def save_json_output(data: Dict, source_file: Path, output_dir: Path, template_name: str = "Employee_Profile"):
    """
    Save extracted data as clean JSON file
    
    Args:
        data: Extracted data dictionary
        source_file: Original source file
        output_dir: Output directory
        template_name: Template name used
    """
    # Create output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / "json" / f"{source_file.stem}_{timestamp}.json"
    
    # Build structured output
    output = {
        "metadata": {
            "source_file": source_file.name,
            "source_path": str(source_file.absolute()),
            "processed_at": datetime.now().isoformat(),
            "template": {
                "name": template_name,
                "confidence": 1.0
            },
            "extraction_method": "Databricks LLM Direct Extraction"
        },
        "data": data
    }
    
        # Save JSON
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    return output_file
def process_file(file_path: Path, output_dir: Path) -> Optional[Path]:
    """
    Process a single file: read → extract → save
    
    Args:
        file_path: Path to input file
        output_dir: Output directory
        
    Returns:
        Path to output JSON file
    """
    print(f"\n{'='*70}")
    print(f"📄 Processing: {file_path.name}")
    print(f"{'='*70}")
    
    try:
        # Step 1: Extract text using appropriate extractor
        print("  📖 Step 1: Extracting text (EasyOCR/Docling)...")
        file_content = extract_file(file_path)
        print(f"  ✅ Extracted {len(file_content)} characters")
        
        # Step 2: Extract with LLM
        print("  🤖 Step 2: Extracting with Databricks LLM...")
        extracted_data = extract_with_llm(file_content)
        
        row_count = len(extracted_data.get("rows", []))
        print(f"  ✅ Extracted {row_count} rows")
        
        # Step 3: Save JSON
        print("  💾 Step 3: Saving JSON output...")
        output_file = save_json_output(extracted_data, file_path, output_dir)
        print(f"  ✅ Saved to: {output_file}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Source: {file_path.name}")
        print(f"   Records: {row_count}")
        print(f"   Output: {output_file.name}")
        
        if row_count > 0:
            sample_fields = list(extracted_data["rows"][0].keys())
            print(f"   Fields: {', '.join(sample_fields[:8])}{'...' if len(sample_fields) > 8 else ''}")
        
        return output_file
        
    except Exception as e:
        print(f"  ❌ Error processing {file_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Direct file extraction to JSON using Databricks LLM"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input file or directory"
    )
    parser.add_argument(
        "--pattern", "-p",
        default="*.csv",
        help="File pattern for directory input (default: *.csv)"
    )
    parser.add_argument(
        "--template", "-t",
        default="Employee_Profile",
        help="Template name (default: Employee_Profile)"
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("🚀 DIRECT FILE EXTRACTION")
    print("="*70)
    print("File → Databricks LLM → JSON")
    print("="*70)
    
    # Setup
    output_dir = ensure_output_dirs()
    print(f"📁 Output directory: {output_dir.absolute()}")
    
    # Determine input files
    input_path = Path(args.input)
    
    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = list(input_path.glob(args.pattern))
    else:
        print(f"❌ Input not found: {input_path}")
        sys.exit(1)
    
    if not files:
        print(f"❌ No files found matching: {args.pattern}")
        sys.exit(1)
    
    print(f"📂 Found {len(files)} file(s)")
    
    # Process each file
    results = []
    for file_path in files:
        output_file = process_file(file_path, output_dir)
        if output_file:
            results.append(output_file)
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE")
    print(f"{'='*70}")
    print(f"Processed: {len(results)}/{len(files)} files")
    print(f"Output: {output_dir / 'json'}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
