"""
PDF Text and Table Extraction Engine
"""

import pdfplumber
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    Extract text and tables from PDF documents
    """
    
    def __init__(self):
        self.supported_extensions = [".pdf"]
    
    def extract_text(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract text from PDF file
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Dictionary with extracted text and metadata
        """
        result = {
            "success": False,
            "text": "",
            "pages": [],
            "page_count": 0,
            "tables": [],
            "error": None
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                result["page_count"] = len(pdf.pages)
                
                all_text = []
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text from page
                    page_text = page.extract_text()
                    
                    if page_text:
                        all_text.append(page_text)
                        result["pages"].append({
                            "page_number": page_num,
                            "text": page_text,
                            "width": page.width,
                            "height": page.height
                        })
                    
                    # Extract tables from page
                    tables = page.extract_tables()
                    if tables:
                        for table_idx, table in enumerate(tables):
                            result["tables"].append({
                                "page_number": page_num,
                                "table_index": table_idx,
                                "data": table
                            })
                
                result["text"] = "\n\n".join(all_text)
                result["success"] = True
                
        except Exception as e:
            logger.error(f"Error extracting PDF {pdf_path}: {e}")
            result["error"] = str(e)
        
        return result
    
    def extract_tables_structured(self, pdf_path: Path) -> List[List[Dict[str, Any]]]:
        """
        Extract tables from PDF with column headers
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            List of tables (each table is list of row dicts)
        """
        structured_tables = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        
                        # First row is headers
                        headers = table[0]
                        
                        # Convert to list of dicts
                        table_data = []
                        for row in table[1:]:
                            if len(row) == len(headers):
                                row_dict = {
                                    headers[i]: row[i] 
                                    for i in range(len(headers))
                                }
                                table_data.append(row_dict)
                        
                        if table_data:
                            structured_tables.append(table_data)
        
        except Exception as e:
            logger.error(f"Error extracting structured tables from {pdf_path}: {e}")
        
        return structured_tables
    
    def extract_with_layout(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract PDF with layout information preserved
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Dictionary with text and layout information
        """
        result = {
            "success": False,
            "pages": [],
            "error": None
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_data = {
                        "page_number": page_num,
                        "text": page.extract_text(),
                        "words": page.extract_words(),
                        "tables": page.extract_tables(),
                    }
                    
                    result["pages"].append(page_data)
                
                result["success"] = True
        
        except Exception as e:
            logger.error(f"Error extracting PDF layout from {pdf_path}: {e}")
            result["error"] = str(e)
        
        return result


