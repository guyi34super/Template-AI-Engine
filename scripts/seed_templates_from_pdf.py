"""
Seed template instruction PDFs into vector database with classification.
This script extracts templates from instruction PDFs and indexes them
so the LLM can reference them when formatting extracted data.
"""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import init_db, SessionLocal
from core.models import Template
from core.templates import create_or_update_template, index_template_text
from extractors.easyocr.easyocr_extractor import EasyOCRExtractor


def extract_pdf_pages(pdf_path: str, use_ocr: bool = True) -> List[str]:
    """
    Extract text from PDF pages using multiple methods.
    
    Args:
        pdf_path: Path to PDF file
        use_ocr: Whether to use OCR extraction
        
    Returns:
        List of page texts
    """
    pages = []
    
    # Try EasyOCR first (most accurate for forms/templates)
    if use_ocr:
        try:
            print(f"  📖 Extracting with EasyOCR...")
            extractor = EasyOCRExtractor(languages=['en'], gpu=False, use_llm_correction=False)
            result = extractor.extract_text_from_pdf(pdf_path)
            
            # Group by page
            page_dict = {}
            for block in result['text_blocks']:
                page_num = block.get('page', 1)
                text = block.get('text', '').strip()
                if page_num not in page_dict:
                    page_dict[page_num] = []
                if text:
                    page_dict[page_num].append(text)
            
            # Convert to list
            for page_num in sorted(page_dict.keys()):
                pages.append('\n'.join(page_dict[page_num]))
            
            if pages and any(p.strip() for p in pages):
                print(f"  ✅ Extracted {len(pages)} pages with EasyOCR")
                return pages
        except Exception as e:
            print(f"  ⚠️  EasyOCR failed: {e}")
    
    # Fallback: PyPDF2
    try:
        from PyPDF2 import PdfReader
        print(f"  📖 Extracting with PyPDF2...")
        reader = PdfReader(pdf_path)
        pages = []
        for i, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
                pages.append(text)
            except Exception as e:
                print(f"  ⚠️  Page {i} extraction failed: {e}")
                pages.append("")
        
        if any(p.strip() for p in pages):
            print(f"  ✅ Extracted {len(pages)} pages with PyPDF2")
            return pages
    except Exception as e:
        print(f"  ⚠️  PyPDF2 failed: {e}")
    
    return []


def detect_template_type(text: str) -> Optional[str]:
    """
    Detect template type from page text using keywords.
    
    Args:
        text: Page text content
        
    Returns:
        Template type name or None
    """
    text_lower = text.lower()
    
    # Define template patterns - Only 4 types from Employee menu
    patterns = {
        "Employee Profile": [
            "employee profile", "employee information", "employee data", 
            "personnel form", "personal information", "employee record",
            "profile", "demographics", "employee details"
        ],
        "Employee Timesheet": [
            "timesheet", "time card", "hours worked", "attendance",
            "clock in", "clock out", "time tracking", "time entry",
            "work hours", "time sheet"
        ],
        "Employee Direct Deposit": [
            "direct deposit", "bank account", "banking information",
            "deposit", "account number", "routing number", "bank details",
            "payment method", "financial institution"
        ],
        "Employee Deductions / Contributions": [
            "deductions", "contributions", "benefits", "withholding",
            "payroll deductions", "retirement", "insurance", "401k",
            "health insurance", "tax withholding", "garnishments"
        ]
    }
    
    # Check each pattern
    scores = {}
    for template_type, keywords in patterns.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            scores[template_type] = score
    
    if not scores:
        return None
    
    # Return highest scoring template
    return max(scores.items(), key=lambda x: x[1])[0]


def find_section_boundaries(pages: List[str]) -> List[tuple]:
    """
    Find section boundaries in multi-template PDFs.
    
    Returns:
        List of (template_type, start_page, end_page)
    """
    sections = []
    current_type = None
    start_page = 0
    
    for i, page_text in enumerate(pages):
        detected_type = detect_template_type(page_text)
        
        if detected_type and detected_type != current_type:
            # Save previous section
            if current_type:
                sections.append((current_type, start_page, i))
            
            # Start new section
            current_type = detected_type
            start_page = i
    
    # Save last section
    if current_type:
        sections.append((current_type, start_page, len(pages)))
    
    return sections


def extract_template_structure(text: str) -> Dict:
    """
    Extract field structure from template text.
    
    Args:
        text: Template text
        
    Returns:
        Dictionary with columns/fields structure
    """
    fields = []
    
    # Look for field patterns like "Field Name:", "Field Name _____", etc.
    field_patterns = [
        r'([A-Z][A-Za-z\s]+):\s*[_\-]{2,}',  # "Field Name: ____"
        r'([A-Z][A-Za-z\s]+)\s+[_\-]{3,}',    # "Field Name ____"
        r'\*?\s*([A-Z][A-Za-z\s]+)\s*:',      # "Field Name:" or "* Field Name:"
    ]
    
    for pattern in field_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            field_name = match.strip()
            if len(field_name) > 2 and field_name not in fields:
                fields.append(field_name)
    
    # Look for table headers
    table_header_pattern = r'^\s*\|\s*(.+?)\s*\|'
    for line in text.split('\n'):
        if match := re.match(table_header_pattern, line):
            headers = [h.strip() for h in match.group(1).split('|')]
            fields.extend([h for h in headers if h and h not in fields])
    
    return {
        "columns": fields[:50],  # Limit to 50 fields
        "field_count": len(fields)
    }


def seed_template_pdf(
    pdf_path: str,
    tenant_id: str = "__system__",
    template_name: Optional[str] = None,
    use_ocr: bool = True
) -> List[str]:
    """
    Seed a template instruction PDF into vector database.
    
    Args:
        pdf_path: Path to PDF file
        tenant_id: Tenant ID for multi-tenancy
        template_name: Override template name
        use_ocr: Whether to use OCR
        
    Returns:
        List of created template IDs
    """
    print(f"\n📄 Processing: {pdf_path}")
    print("="*70)
    
    # Extract pages
    pages = extract_pdf_pages(pdf_path, use_ocr=use_ocr)
    if not pages:
        print(f"  ❌ No text extracted from {pdf_path}")
        return []
    
    print(f"  📊 Extracted {len(pages)} pages")
    
    # Find sections (templates) in the PDF
    sections = find_section_boundaries(pages)
    
    if not sections:
        # Single template PDF
        template_type = template_name or detect_template_type('\n'.join(pages)) or Path(pdf_path).stem
        sections = [(template_type, 0, len(pages))]
    
    print(f"  🔍 Found {len(sections)} template section(s)")
    
    created_ids = []
    
    for template_type, start_page, end_page in sections:
        print(f"\n  📋 Template: {template_type}")
        print(f"     Pages: {start_page + 1}-{end_page}")
        
        # Get section text
        section_pages = pages[start_page:end_page]
        section_text = '\n\n'.join(section_pages)
        
        # Extract structure
        structure = extract_template_structure(section_text)
        print(f"     Fields detected: {structure['field_count']}")
        
        # Create or update template
        template_id = create_or_update_template(
            name=template_type,
            header_json=structure,
            notes=f"Seeded from {Path(pdf_path).name}, pages {start_page + 1}-{end_page}"
        )
        
        # Index pages for vector search
        chunks = [p.strip() for p in section_pages if p.strip()]
        if chunks:
            index_template_text(
                template_id=template_id,
                tenant_id=tenant_id,
                text_chunks=chunks
            )
            print(f"     ✅ Indexed {len(chunks)} chunks into vector DB")
            print(f"     🆔 Template ID: {template_id}")
            created_ids.append(template_id)
        else:
            print(f"     ⚠️  No content to index")
    
    return created_ids


def seed_directory(
    directory: str,
    tenant_id: str = "__system__",
    use_ocr: bool = True
) -> Dict:
    """
    Seed all PDFs in a directory.
    
    Args:
        directory: Directory containing template PDFs
        tenant_id: Tenant ID
        use_ocr: Whether to use OCR
        
    Returns:
        Summary dictionary
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"❌ Directory not found: {directory}")
        return {"success": 0, "failed": 0, "templates": []}
    
    pdf_files = list(dir_path.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ No PDF files found in: {directory}")
        return {"success": 0, "failed": 0, "templates": []}
    
    print(f"📁 Found {len(pdf_files)} PDF file(s)")
    print("="*70)
    
    success = 0
    failed = 0
    all_template_ids = []
    
    for pdf_path in pdf_files:
        try:
            template_ids = seed_template_pdf(str(pdf_path), tenant_id, use_ocr=use_ocr)
            if template_ids:
                success += 1
                all_template_ids.extend(template_ids)
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Error processing {pdf_path.name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        
        print("-"*70)
    
    summary = {
        "success": success,
        "failed": failed,
        "templates": all_template_ids,
        "total_templates": len(all_template_ids)
    }
    
    print(f"\n📊 Seeding Complete")
    print(f"✅ Successful: {success}")
    print(f"❌ Failed: {failed}")
    print(f"📋 Total templates created: {len(all_template_ids)}")
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Seed template instruction PDFs into vector database"
    )
    parser.add_argument(
        "path",
        help="Path to PDF file or directory containing PDFs"
    )
    parser.add_argument(
        "--tenant-id",
        default="__system__",
        help="Tenant ID for multi-tenancy (default: __system__)"
    )
    parser.add_argument(
        "--template-name",
        help="Override template name for single PDF"
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR extraction"
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("📚 TEMPLATE PDF SEEDER")
    print("="*70)
    
    # Initialize database
    init_db()
    
    path = Path(args.path)
    
    if path.is_file():
        # Single PDF
        seed_template_pdf(
            str(path),
            tenant_id=args.tenant_id,
            template_name=args.template_name,
            use_ocr=not args.no_ocr
        )
    elif path.is_dir():
        # Directory of PDFs
        seed_directory(
            str(path),
            tenant_id=args.tenant_id,
            use_ocr=not args.no_ocr
        )
    else:
        print(f"❌ Path not found: {args.path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
