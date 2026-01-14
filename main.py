#!/usr/bin/env python3
"""
Main entry point for AI-Rag Engine with EasyOCR integration
Fast and accurate OCR using EasyOCR for PDFs, Docling for other documents.

Usage:
python .\\main.py --input "..\\files" --out ".\\outdir" --patterns "*.pdf" "*.png" "*.jpg" "*.xlsx" "*.csv" --artifacts-path ".\\tmp_model" --pdf-mode auto --pdf-fallback-ocr 1 --short-text-thresh 50 --docling-tables-from-pdf-text 1 --tables-from-plain-text 1 --use-ocrmypdf 1 --lang "eng" --no-clean --no-clean-final --no-rotate --no-remove-bg --super-ocr 0
"""

import argparse
import os
import sys
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import EasyOCR extractor
try:
    from extractors.easyocr.easyocr_extractor import EasyOCRExtractor
except ImportError:
    print("Warning: Could not import EasyOCRExtractor")
    EasyOCRExtractor = None

# Import document extractors
try:
    from extractors.csv import extract_csv
    from extractors.xlsx import extract_xlsx  
    from extractors.docx import extract_docx
    from extractors.txt import extract_txt
except ImportError as e:
    print(f"Warning: Could not import extractors: {e}")

try:
    from core.db import init_db
except ImportError:
    print("Warning: Could not import init_db")
    def init_db():
        pass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Main document processor: EasyOCR for PDFs, Docling for other formats"""
    
    def __init__(self, args):
        self.args = args
        self.input_dir = Path(args.input)
        self.output_dir = Path(args.out)
        self.artifacts_path = Path(args.artifacts_path)
        self.patterns = args.patterns
        self.pdf_mode = args.pdf_mode
        self.pdf_fallback_ocr = args.pdf_fallback_ocr
        self.short_text_thresh = args.short_text_thresh
        self.lang = args.lang
        self.super_ocr = args.super_ocr
        
        # Initialize EasyOCR for PDFs
        self.easyocr = None
        self._init_easyocr()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        init_db()
        
        logger.info(f"Document processor initialized")
        logger.info(f"Input directory: {self.input_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"📄 PDF files → EasyOCR (fast, accurate)")
        logger.info(f"📄 Other files → Docling (structured extraction)")
    
    def _init_easyocr(self):
        """Initialize EasyOCR extractor for PDFs"""
        try:
            self.easyocr = EasyOCRExtractor(languages=['en'], gpu=False, use_llm_correction=True)
            logger.info("✅ EasyOCR initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ EasyOCR initialization failed: {e}")
            logger.info("Will fall back to docling for PDF processing")
    
    def find_files(self) -> List[Path]:
        """Find all files matching the specified patterns"""
        files = []
        
        for pattern in self.patterns:
            pattern_path = self.input_dir / pattern
            matching_files = glob.glob(str(pattern_path), recursive=True)
            files.extend([Path(f) for f in matching_files])
        
        # Also search recursively
        for pattern in self.patterns:
            pattern_path = self.input_dir / "**" / pattern
            matching_files = glob.glob(str(pattern_path), recursive=True)
            files.extend([Path(f) for f in matching_files])
        
        # Remove duplicates and ensure files exist
        files = list(set(f for f in files if f.is_file()))
        
        logger.info(f"Found {len(files)} files matching patterns: {self.patterns}")
        return files
    
    def get_file_type(self, file_path: Path) -> str:
        """Determine file type from extension"""
        return file_path.suffix.lower().lstrip('.')
    
    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single file using appropriate extractor"""
        logger.info(f"Processing: {file_path.name}")
        
        file_type = self.get_file_type(file_path)
        
        try:
            # Route to appropriate extractor based on file type
            result = self._route_extract(file_type, str(file_path))
            
            # Add processing metadata
            result["metadata"] = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_type": file_type,
                "file_size": file_path.stat().st_size,
                "processor": "EasyOCR" if file_type in ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"] else f"{file_type.upper()} extractor",
                "pdf_mode": self.pdf_mode if file_type == "pdf" else None,
                "ocr_fallback": self.pdf_fallback_ocr if file_type == "pdf" else None,
                "language": self.lang
            }
            
            logger.info(f"✅ Successfully processed {file_path.name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing {file_path.name}: {e}")
            return {
                "error": str(e),
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_type": file_type
            }
    
    def _route_extract(self, file_type: str, path: str) -> Dict[str, Any]:
        """Route file extraction based on file type"""
        
        # Structured documents - use pandas/docling extractors
        if file_type in ("csv",):
            return self._extract_csv(path)
        if file_type in ("xlsx", "xls"):
            return self._extract_xlsx(path)
        if file_type in ("docx", "doc"):
            return self._extract_docx(path)
        if file_type in ("txt",):
            return self._extract_txt(path)
        
        # Visual documents - use EasyOCR
        if file_type in ("pdf",):
            return self._extract_pdf_with_easyocr(path)
        if file_type in ("png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif"):
            return self._extract_image_with_easyocr(path)
        
        raise ValueError(f"Unsupported file type: {file_type}")
    
    def _extract_csv(self, path: str) -> Dict[str, Any]:
        """Extract CSV file"""
        try:
            import pandas as pd
            df = pd.read_csv(path)
            headers = list(df.columns)
            rows = df.astype(str).fillna("").values.tolist()
            return {
                "text_blocks": [],
                "table_blocks": [{"headers": headers, "rows": rows}],
                "header_candidates": headers
            }
        except Exception as e:
            return {
                "text_blocks": [{"page": 1, "text": f"Error processing CSV: {e}"}],
                "table_blocks": [],
                "header_candidates": []
            }
    
    def _extract_xlsx(self, path: str) -> Dict[str, Any]:
        """Extract XLSX file"""
        try:
            import pandas as pd
            xl = pd.ExcelFile(path)
            sheet_name = xl.sheet_names[0]
            df = xl.parse(sheet_name)
            headers = list(df.columns)
            rows = df.astype(str).fillna("").values.tolist()
            return {
                "text_blocks": [],
                "table_blocks": [{"headers": headers, "rows": rows}],
                "header_candidates": headers
            }
        except Exception as e:
            return {
                "text_blocks": [{"page": 1, "text": f"Error processing XLSX: {e}"}],
                "table_blocks": [],
                "header_candidates": []
            }
    
    def _extract_docx(self, path: str) -> Dict[str, Any]:
        """Extract DOCX file"""
        try:
            from docx import Document
            doc = Document(path)
            paragraphs = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    paragraphs.append(paragraph.text.strip())
            
            text_blocks = [{"page": 1, "text": "\n".join(paragraphs)}] if paragraphs else []
            
            header_candidates = []
            for para in paragraphs[:20]:
                if len(para) < 100 and any(keyword in para.lower() for keyword in 
                    ["title", "name", "date", "total", "amount", "number", "id"]):
                    header_candidates.append(para)
            
            return {
                "text_blocks": text_blocks,
                "table_blocks": [],
                "header_candidates": header_candidates[:64]
            }
        except Exception as e:
            return {
                "text_blocks": [{"page": 1, "text": f"Error processing DOCX: {e}"}],
                "table_blocks": [],
                "header_candidates": []
            }
    
    def _extract_txt(self, path: str) -> Dict[str, Any]:
        """Extract TXT file"""
        try:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            lines = content.splitlines()
            text_blocks = [{"page": 1, "text": content}] if content.strip() else []
            
            header_candidates = []
            for line in lines[:50]:
                line = line.strip()
                if line and len(line) < 100:
                    lower_line = line.lower()
                    if any(keyword in lower_line for keyword in [
                        "name", "date", "total", "amount", "number", "id", "title"
                    ]):
                        header_candidates.append(line)
            
            return {
                "text_blocks": text_blocks,
                "table_blocks": [],
                "header_candidates": header_candidates[:64]
            }
        except Exception as e:
            return {
                "text_blocks": [{"page": 1, "text": f"Error processing TXT: {e}"}],
                "table_blocks": [],
                "header_candidates": []
            }
    
    def _extract_image_with_easyocr(self, path: str) -> Dict[str, Any]:
        """Extract text from images using EasyOCR"""
        try:
            if self.easyocr is None:
                raise Exception("EasyOCR not available")
            
            from PIL import Image
            image = Image.open(path)
            text = self.easyocr.extract_text_from_image(image)
            text_blocks = [{"page": 1, "text": text}] if text else []
            
            header_candidates = []
            if text:
                lines = text.splitlines()
                for line in lines[:20]:
                    line = line.strip()
                    if line and len(line) < 100:
                        lower_line = line.lower()
                        if any(keyword in lower_line for keyword in [
                            "invoice", "receipt", "date", "total", "amount", "vendor", 
                            "po", "number", "id", "name", "address", "phone"
                        ]):
                            header_candidates.append(line)
            
            return {
                "text_blocks": text_blocks,
                "table_blocks": [],
                "header_candidates": header_candidates[:64]
            }
        except Exception as e:
            return {
                "text_blocks": [{"page": 1, "text": f"PaddleOCR-VL processing failed: {e}"}],
                "table_blocks": [],
                "header_candidates": []
            }
    
    def _extract_pdf_with_easyocr(self, path: str) -> Dict[str, Any]:
        """Extract text from PDF using EasyOCR"""
        try:
            if self.easyocr is None:
                # Fallback to PyPDF2
                return self._extract_pdf_fallback(path)
                
            # Use the EasyOCR extractor instance
            result = self.easyocr.extract_text_from_pdf(path)
            
            # Extract header candidates from the result
            header_candidates = []
            for tb in result.get("text_blocks", []):
                for line in (tb.get("text", "") or "").splitlines():
                    line = line.strip()
                    if line and len(line) < 100:
                        lower_line = line.lower()
                        if any(keyword in lower_line for keyword in [
                            "invoice", "receipt", "date", "total", "amount", "vendor",
                            "po", "number", "id", "name", "address", "phone", "tax"
                        ]):
                            header_candidates.append(line)
            
            result.setdefault("header_candidates", header_candidates[:64])
            return result
            
        except Exception as e:
            logger.warning(f"EasyOCR PDF extraction failed: {e}, falling back to PyPDF2")
            return self._extract_pdf_fallback(path)
    
    def _extract_pdf_fallback(self, path: str) -> Dict[str, Any]:
        """Fallback PDF extraction using PyPDF2"""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            pages = [(p.extract_text() or "") for p in reader.pages]
            text_blocks = [{"page": i + 1, "text": t or ""} for i, t in enumerate(pages)]
            
            header_candidates = []
            for tb in text_blocks:
                for line in (tb["text"] or "").splitlines():
                    low = line.lower()
                    if any(k in low for k in ["invoice", "date", "total", "tax", "vendor", "amount", "po", "number"]):
                        header_candidates.append(line.strip())
            
            return {
                "text_blocks": text_blocks,
                "table_blocks": [],
                "header_candidates": header_candidates[:64]
            }
        except Exception as e:
            return {
                "text_blocks": [{"page": 1, "text": f"PDF extraction failed: {e}"}],
                "table_blocks": [],
                "header_candidates": []
            }
    
    def save_results(self, file_path: Path, result: Dict[str, Any]):
        """Save processing results to output directory"""
        # Create output filename
        output_filename = file_path.stem + "_extracted.json"
        output_path = self.output_dir / output_filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Results saved: {output_path}")
            
            # Also save text-only version for easy reading
            if result.get("text_blocks"):
                text_output_path = self.output_dir / (file_path.stem + "_text.txt")
                with open(text_output_path, 'w', encoding='utf-8') as f:
                    for block in result["text_blocks"]:
                        f.write(f"=== Page {block.get('page', 1)} ===\n")
                        f.write(block.get('text', '') + "\n\n")
                
                logger.info(f"📄 Text saved: {text_output_path}")
                
        except Exception as e:
            logger.error(f"❌ Error saving results for {file_path.name}: {e}")
    
    def process_all_files(self):
        """Process all files in input directory"""
        files = self.find_files()
        
        if not files:
            logger.warning("No files found matching specified patterns")
            return
        
        results_summary = {
            "processed": 0,
            "errors": 0,
            "total": len(files),
            "files": []
        }
        
        for file_path in files:
            result = self.process_file(file_path)
            
            # Save individual results
            self.save_results(file_path, result)
            
            # Update summary
            if "error" in result:
                results_summary["errors"] += 1
            else:
                results_summary["processed"] += 1
            
            results_summary["files"].append({
                "file": file_path.name,
                "status": "error" if "error" in result else "success",
                "processor": result.get("metadata", {}).get("processor", "unknown")
            })
        
        # Save summary
        summary_path = self.output_dir / "processing_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(results_summary, f, indent=2)
        
        logger.info(f"\n🎯 Processing Complete!")
        logger.info(f"✅ Successfully processed: {results_summary['processed']}")
        logger.info(f"❌ Errors: {results_summary['errors']}")
        logger.info(f"📊 Total files: {results_summary['total']}")
        logger.info(f"💾 Results saved to: {self.output_dir}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="AI-Rag Engine Document Processor with EasyOCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all supported files in a directory
  python main.py --input "../files" --out "./output"
  
  # Process specific file types only
  python main.py --input "../files" --out "./output" --patterns "*.pdf" "*.png"
  
  # With custom OCR settings
  python main.py --input "../files" --out "./output" --pdf-fallback-ocr 1 --lang "eng"
        """
    )
    
    # Input/Output arguments
    parser.add_argument("--input", required=True, 
                       help="Input directory containing files to process")
    parser.add_argument("--out", required=True,
                       help="Output directory for results")
    
    # File pattern arguments
    parser.add_argument("--patterns", nargs="+", 
                       default=["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.xlsx", "*.csv", "*.docx", "*.txt"],
                       help="File patterns to process (default: all supported types)")
    
    # Processing arguments
    parser.add_argument("--artifacts-path", default="./tmp_model",
                       help="Path to artifacts directory")
    parser.add_argument("--pdf-mode", choices=["auto", "ocr", "text"], default="auto",
                       help="PDF processing mode")
    parser.add_argument("--pdf-fallback-ocr", type=int, choices=[0, 1], default=1,
                       help="Use OCR fallback for PDFs (1=yes, 0=no)")
    parser.add_argument("--short-text-thresh", type=int, default=50,
                       help="Short text threshold")
    parser.add_argument("--lang", default="eng",
                       help="OCR language")
    
    # Table extraction arguments
    parser.add_argument("--docling-tables-from-pdf-text", type=int, choices=[0, 1], default=1,
                       help="Extract tables from PDF text using docling")
    parser.add_argument("--tables-from-plain-text", type=int, choices=[0, 1], default=1,
                       help="Extract tables from plain text")
    
    # OCR arguments (kept for compatibility but using LightOnOCR)
    parser.add_argument("--use-ocrmypdf", type=int, choices=[0, 1], default=1,
                       help="Use OCR processing (now using PaddleOCR-VL)")
    parser.add_argument("--super-ocr", type=int, choices=[0, 1], default=0,
                       help="Use enhanced OCR (PaddleOCR-VL is already enhanced)")
    
    # Cleanup arguments
    parser.add_argument("--no-clean", action="store_true",
                       help="Don't clean temporary files")
    parser.add_argument("--no-clean-final", action="store_true", 
                       help="Don't clean final temporary files")
    parser.add_argument("--no-rotate", action="store_true",
                       help="Don't rotate images")
    parser.add_argument("--no-remove-bg", action="store_true",
                       help="Don't remove background")
    
    return parser.parse_args()

def main():
    """Main entry point"""
    print("🚀 AI-Rag Engine Document Processor")
    print("=" * 60)
    print("⚡ Using EasyOCR for fast and accurate text extraction")
    print("=" * 60)
    
    # Parse arguments
    args = parse_arguments()
    
    # Validate input directory
    if not Path(args.input).exists():
        logger.error(f"Input directory does not exist: {args.input}")
        sys.exit(1)
    
    # Initialize processor
    processor = DocumentProcessor(args)
    
    # Process all files
    try:
        processor.process_all_files()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()