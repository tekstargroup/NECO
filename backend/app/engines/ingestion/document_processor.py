"""
Main Document Processing Engine
Orchestrates PDF extraction, Excel parsing, and field detection
"""

from pathlib import Path
from typing import Dict, Any, Optional
import logging
import math

from .pdf_extractor import PDFExtractor
from .excel_parser import ExcelParser
from .docx_extractor import DOCXExtractor
from .field_detector import FieldDetector

logger = logging.getLogger(__name__)


def _needs_line_items_fallback(structured_data: Optional[Dict[str, Any]]) -> bool:
    """True if we should build line_items from Excel because Claude returned none or failed."""
    if not structured_data or not isinstance(structured_data, dict):
        return True
    if structured_data.get("error"):
        return True
    line_items = structured_data.get("line_items")
    return not line_items or not isinstance(line_items, list) or len(line_items) == 0


def _ensure_line_items_from_excel(
    structured_data: Dict[str, Any],
    sheets: list,
) -> Dict[str, Any]:
    """
    Build line_items from Excel sheet rows when Claude returned none.
    Tries (1) column-name mapping, then (2) detect header row when columns are Unnamed.
    """
    out = dict(structured_data)
    out.pop("error", None)
    if not sheets or not sheets[0].get("data"):
        return out
    rows = sheets[0]["data"]
    if not rows:
        return out
    columns = list(rows[0].keys()) if rows else []
    col_lower = {str(c).lower(): c for c in columns}

    def get_col(key: str, *aliases: str):
        for k in (key,) + aliases:
            c = col_lower.get(k.lower())
            if c is not None:
                return c
        return None

    def val(row: dict, c: Any):
        if c is None:
            return None
        v = row.get(c)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return v

    line_items = []
    desc_col = get_col("description", "product", "item", "name", "commodity")
    qty_col = get_col("quantity", "qty", "qty shipped", "units")
    unit_col = get_col("unit", "uom", "unit of measure")
    price_col = get_col("unit_price", "unit price", "price", "rate")
    total_col = get_col("total", "amount", "value", "extended", "line value", "extended value")
    hts_col = get_col("hts", "hts_code", "hts code", "tariff", "harmonized", "hs codes")
    coo_col = get_col("country_of_origin", "origin", "coo", "country", "country of origin")

    _header_keywords = frozenset(
        s.lower().strip()
        for s in (
            "qty", "part no", "description", "country of origin", "eccn", "hs codes",
            "unit price", "extended value", "exporter", "ship from", "invoice no", "invoice date",
            "consignee", "notify party", "final delivery"
        )
    )

    def _looks_like_header(row: dict) -> bool:
        for v in row.values():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            s = str(v).strip().lower()
            if s in _header_keywords or any(s == kw or s.startswith(kw + "\n") or s.endswith("\n" + kw) for kw in _header_keywords):
                return True
        return False

    def _has_numeric(row: dict) -> bool:
        for v in row.values():
            if isinstance(v, (int, float)) and not math.isnan(v) and math.isfinite(v):
                return True
        return False

    if desc_col or qty_col or total_col or price_col:
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if _looks_like_header(row):
                continue
            total = val(row, total_col)
            if total is None and price_col and qty_col:
                try:
                    p, q = float(val(row, price_col) or 0), float(val(row, qty_col) or 0)
                    total = p * q
                except (TypeError, ValueError):
                    pass
            desc = str(val(row, desc_col) or "").strip()
            if not desc and total is None and val(row, qty_col) is None:
                continue
            if not _has_numeric(row):
                continue
            line_items.append({
                "line_number": len(line_items) + 1,
                "description": desc or f"Line {len(line_items) + 1}",
                "quantity": val(row, qty_col),
                "unit": val(row, unit_col),
                "unit_price": val(row, price_col),
                "total": total,
                "hts_code": val(row, hts_col),
                "country_of_origin": val(row, coo_col),
            })

    if not line_items:
        line_items = _build_line_items_from_unnamed_header(rows, columns)
    out["line_items"] = line_items
    return out


def _build_line_items_from_unnamed_header(rows: list, columns: list) -> list:
    """
    Excel was read with default header so columns are Unnamed: 0, 1, 2...
    Find the row whose cell values look like headers (Qty, Description, Unit Price, etc.)
    and use the following rows as line items, mapping by column index.
    """
    header_keywords = {
        "qty": "qty",
        "description": "description",
        "unit price": "unit_price",
        "extended value": "total",
        "extended": "total",
        "hs codes": "hts_code",
        "hs code": "hts_code",
        "country of origin": "country_of_origin",
        "origin": "country_of_origin",
        "part no": "part_no",
    }
    col_keys = {}  # semantic name -> column key (e.g. "Unnamed: 0")
    header_row_idx = None
    for ri, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        found = {}
        for col_key in columns:
            v = row.get(col_key)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            s = str(v).strip().lower()
            for keyword, key in header_keywords.items():
                if keyword in s or s in keyword:
                    found[key] = col_key
                    break
        if "qty" in found and "description" in found:
            col_keys = found
            header_row_idx = ri
            break
    if header_row_idx is None or not col_keys:
        return []

    line_items = []
    for ri in range(header_row_idx + 1, len(rows)):
        row = rows[ri]
        if not isinstance(row, dict):
            continue
        def cell(key: str):
            c = col_keys.get(key)
            if c is None:
                return None
            v = row.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            return v
        qty = cell("qty")
        desc = str(cell("description") or "").strip() if cell("description") is not None else None
        total = cell("total")
        unit_price = cell("unit_price")
        if total is None and unit_price is not None and qty is not None:
            try:
                total = float(unit_price) * float(qty)
            except (TypeError, ValueError):
                pass
        if desc is None and total is None and qty is None:
            break
        has_num = (
            (qty is not None and isinstance(qty, (int, float)) and not math.isnan(qty))
            or (total is not None and isinstance(total, (int, float)) and not math.isnan(total))
            or (unit_price is not None and isinstance(unit_price, (int, float)) and not math.isnan(unit_price))
        )
        if not has_num:
            continue
        line_items.append({
            "line_number": len(line_items) + 1,
            "description": desc or f"Line {len(line_items) + 1}",
            "quantity": qty,
            "unit": None,
            "unit_price": unit_price,
            "total": total,
            "hts_code": cell("hts_code"),
            "country_of_origin": cell("country_of_origin"),
        })
    return line_items


class DocumentProcessor:
    """
    Main document processing engine
    Handles all document types and extracts structured data
    """
    
    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.excel_parser = ExcelParser()
        self.docx_extractor = DOCXExtractor()
        self.field_detector = FieldDetector()
    
    def process_document(self, file_path: Path, document_type_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Process any document and extract structured data.
        
        Args:
            file_path: Path to document
            document_type_hint: Optional type from DB (e.g. ENTRY_SUMMARY, COMMERCIAL_INVOICE).
                               When set, use this for extraction instead of auto-detection.
        Returns:
            Processed document data
        """
        result = {
            "success": False,
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_type": file_path.suffix.lower(),
            "document_type": None,
            "extracted_text": None,
            "structured_data": None,
            "confidence_score": 0,
            "error": None
        }
        
        # Normalize hint to detector's expected values (entry_summary, commercial_invoice, etc.)
        hint_normalized = None
        if document_type_hint:
            h = document_type_hint.strip().upper().replace("-", "_")
            if h == "ENTRY_SUMMARY":
                hint_normalized = "entry_summary"
            elif h == "COMMERCIAL_INVOICE":
                hint_normalized = "commercial_invoice"
            elif h in ("PACKING_LIST", "DATA_SHEET"):
                hint_normalized = "packing_list" if h == "PACKING_LIST" else "other"
        
        try:
            file_ext = file_path.suffix.lower()
            
            # Extract content based on file type
            if file_ext == ".pdf":
                extraction_result = self.pdf_extractor.extract_text(file_path)
                
                if extraction_result["success"]:
                    result["extracted_text"] = extraction_result["text"]
                    result["metadata"] = {
                        "page_count": extraction_result["page_count"],
                        "has_tables": len(extraction_result["tables"]) > 0,
                        "table_count": len(extraction_result["tables"])
                    }
                else:
                    result["error"] = extraction_result["error"]
                    return result
            
            elif file_ext in [".xlsx", ".xls", ".csv"]:
                extraction_result = self.excel_parser.parse_file(file_path)
                
                if extraction_result["success"]:
                    # Convert sheets to text for field detection
                    text_parts = []
                    for sheet in extraction_result["sheets"]:
                        text_parts.append(f"Sheet: {sheet['sheet_name']}")
                        for row in sheet["data"]:
                            text_parts.append(str(row))
                    
                    result["extracted_text"] = "\n".join(text_parts)
                    result["metadata"] = {
                        "sheet_count": len(extraction_result["sheets"]),
                        "sheets": [s["sheet_name"] for s in extraction_result["sheets"]]
                    }
                    result["_excel_sheets"] = extraction_result["sheets"]  # Keep for line_items fallback
                else:
                    result["error"] = extraction_result["error"]
                    return result
            
            elif file_ext == ".docx":
                extraction_result = self.docx_extractor.extract_text(file_path)
                
                if extraction_result["success"]:
                    result["extracted_text"] = extraction_result["text"]
                    result["metadata"] = {
                        "paragraph_count": extraction_result.get("paragraph_count", 0),
                        "table_count": extraction_result.get("table_count", 0),
                    }
                else:
                    result["error"] = extraction_result.get("error", "DOCX extraction failed")
                    return result
            
            else:
                result["error"] = f"Unsupported file type: {file_ext}"
                return result
            
            # Use hint from DB (user categorization) or auto-detect
            if result["extracted_text"]:
                result["document_type"] = hint_normalized or self.field_detector.detect_document_type(
                    result["extracted_text"]
                )
            
            # Extract structured data based on document type
            if result["document_type"] == "commercial_invoice":
                result["structured_data"] = self.field_detector.extract_commercial_invoice_data(
                    result["extracted_text"]
                )
                result["confidence_score"] = 85  # Base confidence for successful extraction
                # Fallback: if Claude returned no line_items, build from Excel sheet data so CI line items are never lost
                if result.get("_excel_sheets") and _needs_line_items_fallback(result["structured_data"]):
                    result["structured_data"] = _ensure_line_items_from_excel(
                        result["structured_data"],
                        result["_excel_sheets"]
                    )
                    logger.info("Commercial invoice: built line_items from Excel sheet (Claude returned none)")
                # When still no line items, expose sheet rows so UI can ask user to select which rows are line items
                if result.get("_excel_sheets") and _needs_line_items_fallback(result["structured_data"]):
                    sheet0 = result["_excel_sheets"][0]
                    rows = sheet0.get("data") or []
                    result["table_preview"] = rows
                    result["table_columns"] = list(rows[0].keys()) if rows else []
            
            elif result["document_type"] == "entry_summary":
                result["structured_data"] = self.field_detector.extract_entry_summary_data(
                    result["extracted_text"]
                )
                result["confidence_score"] = 85
            
            else:
                # Generic field extraction
                result["structured_data"] = {
                    "document_type": result["document_type"],
                    "text_preview": result["extracted_text"][:500] if result["extracted_text"] else None
                }
                result["confidence_score"] = 50  # Lower confidence for generic docs
            
            # Don't pass internal key to callers
            result.pop("_excel_sheets", None)
            result["success"] = True
        
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            result["error"] = str(e)
        
        return result
    
    def process_and_link_documents(
        self,
        commercial_invoice_path: Optional[Path],
        entry_summary_path: Optional[Path]
    ) -> Dict[str, Any]:
        """
        Process and link commercial invoice with entry summary
        
        Args:
            commercial_invoice_path: Path to commercial invoice
            entry_summary_path: Path to entry summary
        
        Returns:
            Combined processed data
        """
        result = {
            "success": False,
            "commercial_invoice": None,
            "entry_summary": None,
            "linked_data": None,
            "error": None
        }
        
        try:
            # Process commercial invoice
            if commercial_invoice_path:
                ci_result = self.process_document(commercial_invoice_path)
                result["commercial_invoice"] = ci_result
            
            # Process entry summary
            if entry_summary_path:
                es_result = self.process_document(entry_summary_path)
                result["entry_summary"] = es_result
            
            # Link the documents
            if result["commercial_invoice"] and result["entry_summary"]:
                result["linked_data"] = self._link_invoice_and_entry(
                    result["commercial_invoice"]["structured_data"],
                    result["entry_summary"]["structured_data"]
                )
            
            result["success"] = True
        
        except Exception as e:
            logger.error(f"Error processing and linking documents: {e}")
            result["error"] = str(e)
        
        return result
    
    def _link_invoice_and_entry(
        self,
        invoice_data: Dict[str, Any],
        entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Link commercial invoice with entry summary line items
        
        Args:
            invoice_data: Processed invoice data
            entry_data: Processed entry data
        
        Returns:
            Linked data structure
        """
        linked = {
            "po_number": invoice_data.get("po_number"),
            "entry_number": entry_data.get("entry_number"),
            "total_invoice_value": invoice_data.get("total_value"),
            "total_entered_value": entry_data.get("total_entered_value"),
            "value_difference": None,
            "line_items": []
        }
        
        # Calculate value difference
        if linked["total_invoice_value"] and linked["total_entered_value"]:
            try:
                linked["value_difference"] = (
                    float(linked["total_entered_value"]) - 
                    float(linked["total_invoice_value"])
                )
            except (ValueError, TypeError):
                pass
        
        # Try to match line items from invoice and entry
        invoice_lines = invoice_data.get("line_items", [])
        entry_lines = entry_data.get("line_items", [])
        
        for entry_line in entry_lines:
            # Find matching invoice line (by description similarity or line number)
            matching_invoice_line = None
            
            for invoice_line in invoice_lines:
                if (entry_line.get("line_number") == invoice_line.get("line_number") or
                    entry_line.get("description", "").lower() in invoice_line.get("description", "").lower()):
                    matching_invoice_line = invoice_line
                    break
            
            linked["line_items"].append({
                "line_number": entry_line.get("line_number"),
                "invoice_data": matching_invoice_line,
                "entry_data": entry_line,
                "hts_code": entry_line.get("hts_code"),
                "description": entry_line.get("description"),
                "entered_value": entry_line.get("entered_value"),
                "invoice_value": matching_invoice_line.get("total") if matching_invoice_line else None,
                "duty_paid": entry_line.get("duty_amount"),
            })
        
        return linked


