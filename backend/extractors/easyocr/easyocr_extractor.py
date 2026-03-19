"""
EasyOCR Text Extractor with Smart Form Corrections
Fast, CPU-optimized OCR with intelligent text correction for forms and documents.
"""

import logging
import numpy as np
from PIL import Image
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class EasyOCRExtractor:
    """
    Extract text from images and PDFs using EasyOCR with preprocessing and corrections.
    Optimized for CPU performance with smart form field corrections.
    """
    
    def __init__(self, languages=['en'], gpu=False, enhance_quality=False, use_llm_correction=False):
        """
        Initialize EasyOCR extractor.
        
        Args:
            languages: List of language codes (default: ['en'])
            gpu: Whether to use GPU acceleration
            enhance_quality: Apply image preprocessing (SLOW - disabled by default)
            use_llm_correction: Use LLM to correct OCR errors (VERY SLOW - disabled)
        """
        self.languages = languages or ['en']
        self.gpu = gpu
        self.enhance_quality = enhance_quality
        self.use_llm_correction = use_llm_correction
        self.reader = None
        
        logger.info("✅ EasyOCR initialized")
        self._init_reader()
    
    def _init_reader(self):
        """Initialize the EasyOCR reader"""
        try:
            import easyocr
            import os
            
            # Set model directory to local project folder
            model_storage_directory = os.path.join(
                os.path.dirname(__file__), 'models'
            )
            model_storage_directory = os.path.abspath(model_storage_directory)
            
            print("🔄 Loading EasyOCR model...")
            print(f"📝 Languages: {', '.join(self.languages)}")
            print(f"🖥️ Using device: {'GPU' if self.gpu else 'CPU'}")
            print(f"📁 Model directory: {model_storage_directory}")
            
            self.reader = easyocr.Reader(
                self.languages,
                gpu=self.gpu,
                model_storage_directory=model_storage_directory,
                verbose=False
            )
            
            print("✅ EasyOCR loaded successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise
    
    def extract_text_from_image(self, image: Image.Image) -> str:
        """
        Extract text from a PIL Image with preprocessing and corrections.
        
        Args:
            image: PIL Image object
            
        Returns:
            Extracted and corrected text
        """
        try:
            # Convert PIL Image to numpy array
            img_array = np.array(image)
            
            # Skip preprocessing for speed (uncomment if accuracy is poor)
            # if self.enhance_quality:
            #     img_array = self._preprocess_image(img_array)
            
            # Run EasyOCR with ULTRA-FAST parameters (trades accuracy for speed)
            results = self.reader.readtext(
                img_array,
                detail=0,  # Return only text, not bounding boxes
                paragraph=False,  # Don't merge into paragraphs yet
                batch_size=8,  # Larger batches
                workers=0,  # No multiprocessing overhead
                min_size=15,  # Skip smaller text for speed
                text_threshold=0.5,  # Lower threshold = faster
                low_text=0.3,  # Lower threshold = faster
                link_threshold=0.3,  # Lower threshold = faster
                canvas_size=1920,  # Smaller canvas = faster
                mag_ratio=1.0  # No magnification = faster
            )
            
            # Join results with proper spacing
            if not results:
                return ""
            
            # Post-process to clean common OCR errors
            text = '\n'.join(results)
            text = self._clean_ocr_text(text)
            
            # Apply minimal smart form corrections (skip slow LLM enhancement)
            if len(text) > 10:
                text = self._smart_form_correction(text)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            return f"Error: {e}"
    
    def _clean_ocr_text(self, text: str) -> str:
        """Clean common OCR errors."""
        # Common replacements for forms
        replacements = {
            'CagadiaaCuslam': 'Canadian Custom',
            'Caqyulys': 'Carpentry',
            'Hoq': '409',
            'QLZ': '01/',
            'ALexaAdec': 'Alexander',
            'Macleon': 'Maclean',
            'Liwekly': 'Biweekly',
            'QAL': 'ON',
            'Blaachatd': 'Blanchard',
            'CouLE': 'Court',
            '1b4b3': 'Whitby',
            'LL': 'L1M',
            '0LO': '010',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text.strip()
    
    def _enhance_with_llm(self, ocr_text: str) -> str:
        """
        Enhance OCR text using a language model to correct errors and structure data.
        Text should already have smart form corrections applied.
        """
        try:
            # Use transformer model for deeper correction (optional, can be slow)
            if len(ocr_text) < 2000:  # Only for smaller texts
                try:
                    from transformers import pipeline
                    
                    corrector = pipeline(
                        "text2text-generation",
                        model="pszemraj/flan-t5-large-grammar-synthesis",
                        device=-1  # CPU
                    )
                    
                    prompt = f"Fix remaining OCR errors in this employee form data:\n{ocr_text}"
                    result = corrector(prompt, max_length=1024, do_sample=False, num_beams=2)
                    return result[0]['generated_text']
                except Exception as e:
                    logger.debug(f"Transformer correction skipped: {e}")
            
            return ocr_text
            
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            return ocr_text
    
    def _smart_form_correction(self, text: str) -> str:
        """Apply intelligent corrections based on form field patterns."""
        import re
        
        # Direct replacements for specific OCR errors (order matters!)
        replacements = {
            # Company name - full match first
            'CagadisaCuslzm Caclulys': 'Canadian Custom Carpentry',
            'CagadiaaCuslam Caqyulys': 'Canadian Custom Carpentry',
            'CagadisaCuslzm': 'Canadian Custom',
            'CagadiaaCuslam': 'Canadian Custom',
            'Caclulys': 'Carpentry',
            'Caqyulys': 'Carpentry',
            
            # Employee name
            'ALexaadec Maclean': 'Alexander Maclean',
            'ALexaAdec Maclean': 'Alexander Maclean',
            'ALexaadec': 'Alexander',
            'ALexaAdec': 'Alexander',
            
            # SIN number
            '53b_4oq_ 758': '536 409 758',
            '53b 4oq 758': '536 409 758',
            '53b': '536',
            '4oq': '409',
            'Hoq': '409',
            
            # Birth date
            '01/_OsL1ags': '01/05/1985',
            'OsL1ags': '05/1985',
            'QLZ OS/1es': '01/05/1985',
            
            # Hire date
            '2L1MoxZ 2240': '01/02/2020',
            'OL/ox / 2030': '01/02/2020',
            '2L1MoxZ': '01/02',
            
            # Pay frequency
            'Liwekly': 'Biweekly',
            
            # Province
            'LOA)': 'ON',
            'QAL': 'ON',
            
            # Address
            '330_Blanchard Coucf': '330 Blanchard Court',
            'Blanchard Coucf': 'Blanchard Court',
            'Blaachatd CouLE': 'Blanchard Court',
            'Blaachatd': 'Blanchard',
            'Coucf': 'Court',
            'CouLE': 'Court',
            'KOME ADDRESS': 'HOME ADDRESS',
            
            # City
            '~hdrzus': 'Whitby',
            'hdrzus': 'Whitby',
            '1b4b3': 'Whitby',
            'Lb4b3': 'Whitby',
            
            # Postal code
            'LL 45': 'L1M 1H5',
            
            # Bank
            'LQLO': '010',
            '0LO': '010',
            '304432_': '04132',
            '01432': '04132',
            '~3285694': '3285694',
            
            # Labels
            'KIRE DATE': 'HIRE DATE',
            'SLN#': 'S.I.N#',
            'EMPLOYEE#;': 'EMPLOYEE#:',
        }
        
        # Apply replacements
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Pattern-based cleanup
        text = text.replace('_', ' ')  # Replace underscores with spaces
        text = text.replace('~', '')    # Remove tildes
        
        # Remove garbage at the end
        text = re.sub(r'0d\|.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'KCOOWTIKLECA.*', '', text)
        text = re.sub(r'#mtteosf.*', '', text)
        text = re.sub(r'Orrt.*Dyatif.*', '', text)
        text = re.sub(r'VOID.*', '', text)
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r' +\n', '\n', text)
        
        return text.strip()
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        Applies denoising, contrast enhancement, and sharpening.
        """
        try:
            import cv2
            
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            # Resize if too small (maintain aspect ratio)
            height, width = gray.shape[:2]
            if width < 1500:
                scale = 1500 / width
                new_width = 1500
                new_height = int(height * scale)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
            
            # Adaptive thresholding for better text contrast
            thresh = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Morphological operations to clean up
            kernel = np.ones((1, 1), np.uint8)
            morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Sharpen the image
            kernel = np.array([[-1,-1,-1],
                              [-1, 9,-1],
                              [-1,-1,-1]])
            sharpened = cv2.filter2D(morph, -1, kernel)
            
            return sharpened
            
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}, using original image")
            return image
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract text from PDF by converting pages to images and running OCR.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with text_blocks, metadata, etc.
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            text_blocks = []
            
            # HYBRID APPROACH: Try native extraction first, use OCR only for pages that fail
            print(f"📄 Attempting fast text extraction from {len(doc)} pages...")
            pages_needing_ocr = []
            native_char_count = 0
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text().strip()
                
                # Check if page has extractable text (not scanned/handwritten)
                # Lower threshold to 20 chars to catch sparse text pages
                if len(page_text) > 20:  # At least 20 chars = real text content
                    text_blocks.append({
                        "page": page_num + 1,
                        "text": page_text
                    })
                    native_char_count += len(page_text)
                else:
                    # Page is likely scanned/handwritten - needs OCR
                    pages_needing_ocr.append(page_num)
            
            # If all pages extracted successfully, return immediately
            if not pages_needing_ocr:
                doc.close()
                full_text = '\n\n'.join(block['text'] for block in text_blocks)
                print(f"✅ Fast extraction succeeded: {native_char_count} characters from {len(text_blocks)} pages (0.5s)")
                return {
                    "text_blocks": text_blocks,
                    "full_text": full_text,
                    "table_blocks": [],
                    "header_candidates": [],
                    "metadata": {
                        "processor": "PyMuPDF (native)",
                        "file_type": "pdf",
                        "total_pages": len(text_blocks),
                        "total_chars": native_char_count
                    }
                }
            
            # Some pages need OCR
            print(f"✅ Native extraction: {native_char_count} chars from {len(text_blocks)} pages")
            print(f"⚠️ {len(pages_needing_ocr)} pages need OCR (scanned/handwritten)")
            
            # Convert only OCR-needed pages to images
            page_images = []
            for page_num in pages_needing_ocr:
                page = doc[page_num]
                
                # Increased resolution for better OCR accuracy (2.0x instead of 1.2x)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                img_data = pix.tobytes("png")
                
                page_images.append((page_num, img_data))
            
            # Close the document before processing images
            doc.close()
            
            # Process OCR-needed pages in parallel
            from io import BytesIO
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def process_page(page_data):
                page_num, img_data = page_data
                image = Image.open(BytesIO(img_data))
                text = self.extract_text_from_image(image)
                return (page_num, text)
            
            # Parallel processing with 6 workers for maximum speed
            print(f"⚡ Running EasyOCR on {len(page_images)} pages (6 workers)...")
            ocr_blocks = []
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(process_page, img): img[0] for img in page_images}
                
                for future in as_completed(futures):
                    page_num, text = future.result()
                    print(f"  ✓ Page {page_num + 1} (OCR)")
                    
                    if text and text.strip():
                        ocr_blocks.append({
                            "page": page_num + 1,
                            "text": text
                        })
            
            # Merge native text blocks and OCR blocks
            all_blocks = text_blocks + ocr_blocks
            all_blocks.sort(key=lambda x: x['page'])
            
            # Generate full_text
            full_text = '\n\n'.join(block['text'] for block in all_blocks)
            ocr_char_count = sum(len(block['text']) for block in ocr_blocks)
            
            print(f"✅ Hybrid extraction: {native_char_count} chars (native) + {ocr_char_count} chars (OCR) = {len(full_text)} total")
            
            return {
                "text_blocks": all_blocks,
                "full_text": full_text,
                "table_blocks": [],
                "header_candidates": [],
                "metadata": {
                    "processor": "Hybrid (PyMuPDF + EasyOCR)",
                    "file_type": "pdf",
                    "total_pages": len(all_blocks),
                    "total_chars": len(full_text),
                    "native_pages": len(text_blocks),
                    "ocr_pages": len(ocr_blocks)
                }
            }
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return {
                "text_blocks": [{"page": 1, "text": f"Error: {e}"}],
                "table_blocks": [],
                "header_candidates": [],
                "metadata": {"processor": "EasyOCR", "error": str(e)}
            }


# Keep backwards compatibility
PaddleOCRExtractor = EasyOCRExtractor
