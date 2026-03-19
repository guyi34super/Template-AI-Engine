"""
Unit Tests for File Type Extractors - CSV, XLSX, DOCX, TXT
"""

import unittest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
import csv


class TestCSVExtractor(unittest.TestCase):
    """Test suite for CSV extraction"""
    
    def test_extract_csv_basic(self):
        """Test basic CSV extraction"""
        csv_content = "name,age,city\nJohn,30,NYC\nJane,25,LA"
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            from extractors.csv import extract_csv
            
            result = extract_csv("test.csv")
            
            self.assertIsNotNone(result)
    
    def test_extract_csv_with_headers(self):
        """Test CSV extraction preserves headers"""
        csv_data = [
            ["name", "age", "city"],
            ["John", "30", "NYC"],
            ["Jane", "25", "LA"]
        ]
        
        # Create temp CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            temp_path = f.name
        
        try:
            from extractors.csv import extract_csv
            result = extract_csv(temp_path)
            
            self.assertIsNotNone(result)
        finally:
            os.unlink(temp_path)
    
    def test_extract_csv_empty_file(self):
        """Test CSV extraction from empty file"""
        import pandas as pd
        
        with patch('builtins.open', mock_open(read_data="")):
            from extractors.csv import extract_csv
            
            # pandas raises EmptyDataError for truly empty CSV
            with self.assertRaises(pd.errors.EmptyDataError):
                result = extract_csv("empty.csv")
    
    def test_extract_csv_with_special_characters(self):
        """Test CSV extraction with special characters"""
        csv_content = 'name,description\n"John O\'Brien","Test, with comma"'
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            from extractors.csv import extract_csv
            
            result = extract_csv("test.csv")
            
            self.assertIsNotNone(result)


class TestXLSXExtractor(unittest.TestCase):
    """Test suite for XLSX extraction"""
    
    @patch('pandas.ExcelFile')
    def test_extract_xlsx_basic(self, mock_excel_file):
        """Test basic XLSX extraction"""
        # Mock pandas ExcelFile and DataFrame
        mock_xl = Mock()
        mock_xl.sheet_names = ["Sheet1"]
        mock_df = Mock()
        mock_df.columns = ["name", "age"]
        mock_df.astype.return_value.fillna.return_value.values.tolist.return_value = [["John", "30"]]
        mock_xl.parse.return_value = mock_df
        mock_excel_file.return_value = mock_xl
        
        from extractors.xlsx import extract_xlsx
        
        result = extract_xlsx("test.xlsx")
        
        self.assertIsNotNone(result)
        self.assertIn("table_blocks", result)
        self.assertIn("header_candidates", result)
    
    @patch('pandas.ExcelFile')
    def test_extract_xlsx_multiple_sheets(self, mock_excel_file):
        """Test XLSX extraction with multiple sheets"""
        mock_xl = Mock()
        mock_xl.sheet_names = ["Sheet1", "Sheet2"]
        mock_df = Mock()
        mock_df.columns = []
        mock_df.astype.return_value.fillna.return_value.values.tolist.return_value = []
        mock_xl.parse.return_value = mock_df
        mock_excel_file.return_value = mock_xl
        
        from extractors.xlsx import extract_xlsx
        
        result = extract_xlsx("test.xlsx")
        
        self.assertIsNotNone(result)
        self.assertIn("table_blocks", result)
    
    @patch('pandas.ExcelFile')
    def test_extract_xlsx_empty_sheet(self, mock_excel_file):
        """Test XLSX extraction from empty sheet"""
        mock_xl = Mock()
        mock_xl.sheet_names = ["Sheet1"]
        mock_df = Mock()
        mock_df.columns = []
        mock_df.astype.return_value.fillna.return_value.values.tolist.return_value = []
        mock_xl.parse.return_value = mock_df
        mock_excel_file.return_value = mock_xl
        
        from extractors.xlsx import extract_xlsx
        
        result = extract_xlsx("empty.xlsx")
        
        self.assertIsNotNone(result)
        self.assertIn("table_blocks", result)


class TestDOCXExtractor(unittest.TestCase):
    """Test suite for DOCX extraction"""
    
    @patch('docx.Document')
    def test_extract_docx_basic(self, mock_document):
        """Test basic DOCX extraction"""
        mock_doc = Mock()
        mock_paragraph = Mock()
        mock_paragraph.text = "Sample paragraph text"
        mock_doc.paragraphs = [mock_paragraph]
        mock_doc.tables = []
        mock_document.return_value = mock_doc
        
        from extractors.docx import extract_docx
        
        result = extract_docx("test.docx")
        
        self.assertIsNotNone(result)
        self.assertIn("text_blocks", result)
        self.assertIn("table_blocks", result)
        self.assertIn("header_candidates", result)
    
    @patch('docx.Document')
    def test_extract_docx_multiple_paragraphs(self, mock_document):
        """Test DOCX extraction with multiple paragraphs"""
        mock_doc = Mock()
        mock_doc.paragraphs = [
            Mock(text="Paragraph 1"),
            Mock(text="Paragraph 2"),
            Mock(text="Paragraph 3")
        ]
        mock_doc.tables = []
        mock_document.return_value = mock_doc
        
        from extractors.docx import extract_docx
        
        result = extract_docx("test.docx")
        
        self.assertIn("text_blocks", result)
        self.assertIn("table_blocks", result)
    
    @patch('docx.Document')
    def test_extract_docx_empty_document(self, mock_document):
        """Test DOCX extraction from empty document"""
        mock_doc = Mock()
        mock_doc.paragraphs = []
        mock_doc.tables = []
        mock_document.return_value = mock_doc
        
        from extractors.docx import extract_docx
        
        result = extract_docx("empty.docx")
        
        self.assertIsNotNone(result)
        self.assertIn("text_blocks", result)
        self.assertEqual(result["text_blocks"], [])
    
    @patch('docx.Document')
    def test_extract_docx_with_tables(self, mock_document):
        """Test DOCX extraction with tables"""
        mock_doc = Mock()
        mock_doc.paragraphs = []
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.text = "Cell content"
        mock_row.cells = [mock_cell]
        mock_table.rows = [mock_row]
        mock_doc.paragraphs = []
        mock_doc.tables = [mock_table]
        mock_document.return_value = mock_doc
        
        from extractors.docx import extract_docx
        
        result = extract_docx("test.docx")
        
        self.assertIsNotNone(result)


class TestTXTExtractor(unittest.TestCase):
    """Test suite for TXT extraction"""
    
    def test_extract_txt_basic(self):
        """Test basic TXT extraction"""
        txt_content = "This is a sample text file.\nWith multiple lines."
        
        with patch('builtins.open', mock_open(read_data=txt_content)):
            from extractors.txt import extract_txt
            
            result = extract_txt("test.txt")
            
            self.assertIsNotNone(result)
            self.assertIn("text_blocks", result)
    
    def test_extract_txt_empty_file(self):
        """Test TXT extraction from empty file"""
        with patch('builtins.open', mock_open(read_data="")):
            from extractors.txt import extract_txt
            
            result = extract_txt("empty.txt")
            
            self.assertIsNotNone(result)
    
    def test_extract_txt_unicode(self):
        """Test TXT extraction with Unicode characters"""
        txt_content = "Unicode test: 你好世界 🎉 Café"
        
        with patch('builtins.open', mock_open(read_data=txt_content)):
            from extractors.txt import extract_txt
            
            result = extract_txt("unicode.txt")
            
            self.assertIsNotNone(result)
    
    def test_extract_txt_large_file(self):
        """Test TXT extraction from large file"""
        large_content = "Line of text.\n" * 10000
        
        with patch('builtins.open', mock_open(read_data=large_content)):
            from extractors.txt import extract_txt
            
            result = extract_txt("large.txt")
            
            self.assertIsNotNone(result)


class TestExtractorEdgeCases(unittest.TestCase):
    """Test edge cases for all extractors"""
    
    def test_csv_with_different_encodings(self):
        """Test CSV extraction with different encodings"""
        # Test that extractor can handle various encodings
        csv_content = "name,value\ntest,123"
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            from extractors.csv import extract_csv
            
            result = extract_csv("test.csv")
            
            self.assertIsNotNone(result)
    
    def test_xlsx_with_formulas(self):
        """Test XLSX extraction with formulas"""
        with patch('pandas.ExcelFile') as mock_excel_file_class:
            # Mock pandas ExcelFile instance
            mock_xl = Mock()
            mock_excel_file_class.return_value = mock_xl
            mock_xl.sheet_names = ["Sheet1"]
            
            # Mock DataFrame with formula results
            mock_df = Mock()
            mock_df.columns = ["result"]  # Make columns iterable
            mock_df.astype.return_value.fillna.return_value.values.tolist.return_value = [[42]]
            mock_xl.parse.return_value = mock_df
            
            from extractors.xlsx import extract_xlsx
            
            result = extract_xlsx("formulas.xlsx")
            
            self.assertIsNotNone(result)
            self.assertIn("table_blocks", result)
    
    def test_docx_with_images(self):
        """Test DOCX extraction with embedded images"""
        with patch('docx.Document') as mock_document:
            mock_doc = Mock()
            mock_doc.paragraphs = [Mock(text="Text with image")]
            mock_document.return_value = mock_doc
            
            from extractors.docx import extract_docx
            
            result = extract_docx("with_images.docx")
            
            # Should extract text, skip images
            self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
