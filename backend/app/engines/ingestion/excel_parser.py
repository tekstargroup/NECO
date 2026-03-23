"""
Excel/CSV Parser Engine
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ExcelParser:
    """
    Parse Excel and CSV files
    """
    
    def __init__(self):
        self.supported_extensions = [".xlsx", ".xls", ".csv"]
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse Excel or CSV file
        
        Args:
            file_path: Path to file
        
        Returns:
            Dictionary with parsed data
        """
        result = {
            "success": False,
            "sheets": [],
            "error": None
        }
        
        try:
            file_ext = file_path.suffix.lower()
            
            if file_ext == ".csv":
                # Parse CSV
                df = pd.read_csv(file_path)
                result["sheets"].append({
                    "sheet_name": "Sheet1",
                    "data": df.to_dict(orient="records"),
                    "columns": list(df.columns),
                    "row_count": len(df)
                })
            
            else:
                # Parse Excel (may have multiple sheets)
                excel_file = pd.ExcelFile(file_path)
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    result["sheets"].append({
                        "sheet_name": sheet_name,
                        "data": df.to_dict(orient="records"),
                        "columns": list(df.columns),
                        "row_count": len(df)
                    })
            
            result["success"] = True
        
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            result["error"] = str(e)
        
        return result
    
    def extract_tables(self, file_path: Path) -> List[pd.DataFrame]:
        """
        Extract all tables as DataFrames
        
        Args:
            file_path: Path to file
        
        Returns:
            List of DataFrames
        """
        tables = []
        
        try:
            file_ext = file_path.suffix.lower()
            
            if file_ext == ".csv":
                df = pd.read_csv(file_path)
                tables.append(df)
            else:
                excel_file = pd.ExcelFile(file_path)
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    tables.append(df)
        
        except Exception as e:
            logger.error(f"Error extracting tables from {file_path}: {e}")
        
        return tables
    
    def find_table_by_header(self, file_path: Path, header_keywords: List[str]) -> Optional[pd.DataFrame]:
        """
        Find a table that contains specific header keywords
        
        Args:
            file_path: Path to file
            header_keywords: Keywords to search for in headers
        
        Returns:
            DataFrame if found, None otherwise
        """
        try:
            tables = self.extract_tables(file_path)
            
            for df in tables:
                columns_lower = [str(col).lower() for col in df.columns]
                
                # Check if any keyword matches any column
                for keyword in header_keywords:
                    if any(keyword.lower() in col for col in columns_lower):
                        return df
        
        except Exception as e:
            logger.error(f"Error finding table in {file_path}: {e}")
        
        return None


