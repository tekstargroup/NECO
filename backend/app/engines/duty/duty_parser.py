"""
Duty Parsing Engine - Sprint 5 Phase 2

Lossless parsing of duty rates from HTS tariff text.
Preserves all legal meaning, never discards text.

Core Principles:
- Never discard legal text
- Store structure even if not computable
- Assign confidence levels based on parsing certainty
- No inheritance resolution (Phase 3)
- No trade program resolution (Phase 3)
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from app.models.duty_rate import DutyType, DutyConfidence, DutySourceLevel

logger = logging.getLogger(__name__)


@dataclass
class ParsedDutyRate:
    """
    Result of parsing a duty rate from HTS text.
    This is an intermediate representation before creating DutyRate model instances.
    """
    raw_text: str  # Original text, never modified
    duty_type: DutyType
    duty_confidence: DutyConfidence
    structure: Dict[str, Any]  # Structured interpretation (JSONB-compatible)
    numeric_value: Optional[float]  # Computable value if available
    is_free: bool
    parse_errors: List[str]  # Any parsing issues (for logging/audit)
    parse_method: str  # How this was parsed (for audit)


class DutyParser:
    """
    Lossless duty rate parser.
    
    Parses duty rates from HTS tariff text while preserving all legal meaning.
    Never discards original text.
    """
    
    # Patterns for different duty types
    FREE_PATTERNS = [
        r'^\s*free\s*$',  # "Free"
        r'^\s*free\s*\(',  # "Free (..."
        r'free\s*$',  # "...free"
    ]
    
    AD_VALOREM_PATTERNS = [
        r'(\d+\.?\d*)\s*%',  # "4.9%"
        r'(\d+\.?\d*)\s*percent',  # "4.9 percent"
        r'(\d+\.?\d*)\s*per\s+cent',  # "4.9 per cent"
    ]
    
    SPECIFIC_PATTERNS = [
        r'\$\s*(\d+\.?\d*)\s*/\s*([a-z]+)',  # "$0.50/kg"
        r'(\d+\.?\d*)\s*\$?\s*/\s*([a-z]+)',  # "0.50/kg" or "0.50 $/kg"
        r'(\d+\.?\d*)\s*per\s+([a-z]+)',  # "0.50 per kg"
        r'(\d+\.?\d*)\s*\$',  # "0.50$" (unit may be elsewhere)
        r'(\d+\.?\d*)\s*¢\s*/\s*([a-z]+)',  # "6.6¢/kg"
        r'(\d+\.?\d*)\s*cents?\s*/\s*([a-z]+)',  # "6.6 cents/kg"
    ]
    
    COMPOUND_PATTERNS = [
        r'(\d+\.?\d*)\s*%\s*\+\s*\$?\s*(\d+\.?\d*)\s*/?\s*([a-z]*)',  # "4.9% + $0.50/kg"
        r'(\d+\.?\d*)\s*%\s*and\s+\$?\s*(\d+\.?\d*)\s*/?\s*([a-z]*)',  # "4.9% and $0.50/kg"
        r'(\d+\.?\d*)\s*%\s*plus\s+\$?\s*(\d+\.?\d*)\s*/?\s*([a-z]*)',  # "4.9% plus $0.50/kg"
        r'(\d+\.?\d*)\s*¢\s*/\s*([a-z]+)\s*\+\s*(\d+\.?\d*)\s*%',  # "15.4¢/kg + 45%"
        r'(\d+\.?\d*)\s*¢\s*/\s*([a-z]+)\s*and\s+(\d+\.?\d*)\s*%',  # "15.4¢/kg and 45%"
    ]
    
    CONDITIONAL_PATTERNS = [
        r'see\s+subheading\s+(\d+\.?\d*\.?\d*\.?\d*)',  # "See subheading 1234.56.78"
        r'see\s+heading\s+(\d+)',  # "See heading 1234"
        r'see\s+note\s+(\d+)',  # "See note 2"
        r'as\s+provided\s+for\s+in',  # "As provided for in..."
        r'subject\s+to\s+note',  # "Subject to note..."
    ]
    
    # Unit normalization map (normalize variations to standard codes)
    UNIT_NORMALIZATION = {
        # Weight
        'kg': 'kg', 'kilogram': 'kg', 'kilograms': 'kg', 'kgs': 'kg',
        'g': 'g', 'gram': 'g', 'grams': 'g', 'gr': 'g',
        'lb': 'lb', 'pound': 'lb', 'pounds': 'lb', 'lbs': 'lb',
        'oz': 'oz', 'ounce': 'oz', 'ounces': 'oz',
        
        # Length/Area/Volume
        'm': 'm', 'meter': 'm', 'metre': 'm', 'meters': 'm', 'metres': 'm',
        'cm': 'cm', 'centimeter': 'cm', 'centimetre': 'cm',
        'm2': 'm2', 'sqm': 'm2', 'square meter': 'm2', 'square metre': 'm2',
        'm3': 'm3', 'cubic meter': 'm3', 'cubic metre': 'm3',
        
        # Count/Units
        'no': 'no', 'number': 'no', 'numbers': 'no', 'nos': 'no',
        'pcs': 'pcs', 'piece': 'pcs', 'pieces': 'pcs',
        'pair': 'pair', 'pairs': 'pair',
        'set': 'set', 'sets': 'set',
    }
    
    # Quantity basis inference from unit
    QUANTITY_BASIS_MAP = {
        'kg': 'net_weight', 'g': 'net_weight', 'lb': 'net_weight', 'oz': 'net_weight',
        'm': 'length', 'cm': 'length',
        'm2': 'area',
        'm3': 'volume',
        'no': 'units', 'pcs': 'units', 'piece': 'units', 'pair': 'units', 'set': 'units',
    }
    
    def parse_duty_rate(
        self,
        raw_text: str,
        hts_code: Optional[str] = None,
        source_level: Optional[DutySourceLevel] = None,
    ) -> ParsedDutyRate:
        """
        Main parsing method. Routes to appropriate parser based on text content.
        
        Uses two-line interpretation model:
        - Line 1: Primary rate expression
        - Line 2+: Secondary program notes (e.g., "Free (A+, AU, ...)")
        
        Args:
            raw_text: Raw duty rate text from HTS (verbatim, never cleaned)
            hts_code: HTS code (for context/logging)
            source_level: Source precision level (for context/logging)
        
        Returns:
            ParsedDutyRate with structure and confidence level
        """
        if not raw_text or not raw_text.strip():
            return ParsedDutyRate(
                raw_text=raw_text or "",
                duty_type=DutyType.TEXT_ONLY,
                duty_confidence=DutyConfidence.LOW,
                structure={"text": raw_text or "", "error": "empty_text"},
                numeric_value=None,
                is_free=False,
                parse_errors=["Empty or null duty text"],
                parse_method="empty_text_fallback"
            )
        
        # Preserve original text exactly (never clean)
        original_text = raw_text.strip()
        
        # Normalize lines: split, strip, collapse dot leaders
        lines = self._normalize_lines(original_text)
        primary_line = lines[0] if lines else ""
        secondary_lines = lines[1:] if len(lines) > 1 else []
        
        # Try parsing in order of specificity (most specific first)
        # 1. Free (check primary line first - if Free, it's primary)
        free_result = self._parse_free_duty(primary_line, secondary_lines, original_text)
        if free_result:
            return free_result
        
        # 2. Check for same-line dual-rate patterns: "X% Free (programs)" or "Y¢/kg Free (programs)"
        # This is MFN rate + Free under special programs
        dual_rate_result = self._parse_dual_rate_free(primary_line, original_text)
        if dual_rate_result:
            # Check for additional secondary Free notes
            self._attach_secondary_free_programs(dual_rate_result, secondary_lines)
            dual_rate_result.raw_text = original_text  # Preserve full original text
            return dual_rate_result
        
        # 3. Compound (most complex, check before simple patterns)
        compound_result = self._parse_compound_duty(primary_line)
        if compound_result:
            # Check for secondary Free notes
            self._attach_secondary_free_programs(compound_result, secondary_lines)
            compound_result.raw_text = original_text  # Preserve full original text
            return compound_result
        
        # 4. Conditional (check before ad valorem/specific)
        conditional_result = self._parse_conditional_duty(primary_line)
        if conditional_result:
            self._attach_secondary_free_programs(conditional_result, secondary_lines)
            conditional_result.raw_text = original_text  # Preserve full original text
            return conditional_result
        
        # 5. Ad valorem
        ad_valorem_result = self._parse_ad_valorem_duty(primary_line)
        if ad_valorem_result:
            # Check for secondary Free notes
            self._attach_secondary_free_programs(ad_valorem_result, secondary_lines)
            ad_valorem_result.raw_text = original_text  # Preserve full original text
            return ad_valorem_result
        
        # 6. Specific
        specific_result = self._parse_specific_duty(primary_line)
        if specific_result:
            # Check for secondary Free notes
            self._attach_secondary_free_programs(specific_result, secondary_lines)
            specific_result.raw_text = original_text  # Preserve full original text
            return specific_result
        
        # 7. Fallback: Text-only (preserve everything)
        return self._parse_text_only_duty(original_text)
    
    def _normalize_lines(self, text: str) -> List[str]:
        """
        Normalize duty text into lines: split, strip, collapse dot leaders.
        
        Also filters out lines that are clearly HTS codes or section headers
        to find the actual duty rate line. Prioritizes lines that look like
        duty rates (contain "Free", "%", "$", "¢", etc.).
        
        Returns list of non-empty lines, with duty-relevant lines prioritized.
        """
        all_lines = []
        duty_like_lines = []
        
        for line in text.split('\n'):
            # Strip whitespace
            line = line.strip()
            # Collapse dot leaders (multiple dots/periods)
            line = re.sub(r'\.{3,}', '...', line)
            # Skip empty lines
            if not line:
                continue
            
            # Skip lines that are clearly HTS codes (e.g., "0101.21.00", "8518.30.10")
            if re.match(r'^\d{4}\.?\d{2}\.?\d{2}', line):
                continue
            
            # Skip lines that are section headers (e.g., "General", "Special", "Chapter 85")
            if re.match(r'^(General|Special|Chapter|Heading|Subheading)', line, re.IGNORECASE):
                continue
            
            # Skip lines that are just numbers with "No." (table formatting)
            if re.match(r'^\d+\s*No\.?\s*$', line, re.IGNORECASE):
                continue
            
            # Phase 2.3: Handle lines starting with "00" - extract text after "00"
            if re.match(r'^\s*0{2,}\s+', line):
                # Extract the actual duty text after "00"
                line = re.sub(r'^\s*0{2,}\s+', '', line)
                # Collapse dot leaders again after removal
                line = re.sub(r'\.{3,}', '...', line)
                if not line.strip():
                    continue
            
            # Phase 2.3: If line begins with digits and contains no duty tokens, skip it
            DUTY_TOKENS = r'(free|%|\$|¢|cents?|per\s+(kg|lb|piece|unit|liter|head))'
            if re.match(r'^\d', line):
                if not re.search(DUTY_TOKENS, line, re.IGNORECASE):
                    continue
            
            # Phase 2.3: Skip lines that are mostly digits/spaces/punctuation without duty tokens
            # (short lines that are likely table formatting)
            if len(line) < 50:  # Short line threshold
                non_digit_chars = len(re.sub(r'[\d\s\.\,\:\;\(\)]', '', line))
                if non_digit_chars < 3 and not re.search(DUTY_TOKENS, line, re.IGNORECASE):
                    continue
            
            # Phase 2.3: Normalize duplicate Free tokens and standalone "Free" with dots
            # "Free Free" or "Free\nFree" -> "Free"
            line = re.sub(r'\bfree\s+free\b', 'Free', line, flags=re.IGNORECASE)
            line = re.sub(r'\bfree\bfree\b', 'Free', line, flags=re.IGNORECASE)
            # "... Free" or "Free ..." -> "Free" (standalone Free with dot leaders)
            if re.match(r'^\.+\s*free\.?\s*$', line, re.IGNORECASE) or re.match(r'^\s*free\.?\s*\.+$', line, re.IGNORECASE):
                line = 'Free'
            
            # Check if line looks like a duty rate (contains Free, %, $, ¢, etc.)
            is_duty_like = bool(re.search(DUTY_TOKENS, line, re.IGNORECASE))
            
            if is_duty_like:
                duty_like_lines.append(line)
            else:
                all_lines.append(line)
        
        # Prioritize duty-like lines, then other lines
        if duty_like_lines:
            return duty_like_lines + all_lines
        
        # If no duty-like lines found, return all filtered lines
        if all_lines:
            return all_lines
        
        # Fallback: return original lines without filtering
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            line = re.sub(r'\.{3,}', '...', line)
            if line:
                lines.append(line)
        return lines
    
    def _parse_dual_rate_free(self, text: str, original_text: str) -> Optional[ParsedDutyRate]:
        """
        Parse same-line dual-rate patterns: "X% Free (programs)" or "Y¢/kg Free (programs)".
        
        Phase 2.3: These represent MFN rate + Free under special programs.
        
        Examples:
        - "25% Free (A+, AU, BH...)" → AD_VALOREM with secondary_free_programs
        - "5.5¢/kg Free (A+, AU...)" → SPECIFIC with secondary_free_programs
        
        Returns:
            ParsedDutyRate with primary rate type and secondary_free_programs in structure.
            NOT FREE as base rate, NOT TEXT_ONLY.
        """
        text_lower = text.lower()
        
        # Pattern 1: "X% Free (programs)" or "Free (programs), X%"
        # Try "X% Free" first
        ad_valorem_dual = re.search(r'(\d+\.?\d*)\s*%\s+free\s*(?:\(([^)]+)\))?', text_lower, re.IGNORECASE)
        if not ad_valorem_dual:
            # Try "Free (programs), X%" - handle incomplete parens
            ad_valorem_dual = re.search(r'free\s*\(([^)]+)\)[^%]*(\d+\.?\d*)\s*%', text_lower, re.IGNORECASE)
            if not ad_valorem_dual:
                # Try "Free (programs, X%" (incomplete paren, rate in programs list)
                ad_valorem_dual = re.search(r'free\s*\(([^,]+(?:,\s*[^,]+)*),\s*(\d+\.?\d*)\s*[¢\$]', text_lower, re.IGNORECASE)
            if ad_valorem_dual:
                # Swap groups: programs is group 1, percentage is group 2
                programs_text = ad_valorem_dual.group(1)
                percentage = float(ad_valorem_dual.group(2))
                programs = [p.strip() for p in programs_text.split(',')] if programs_text else []
                
                structure = {
                    "percentage": percentage,
                    "secondary_free_programs": programs,
                    "special_rate_free": True,
                    "eligibility_note_raw": ad_valorem_dual.group(0)
                }
                
                return ParsedDutyRate(
                    raw_text=original_text,
                    duty_type=DutyType.AD_VALOREM,
                    duty_confidence=DutyConfidence.HIGH,
                    structure=structure,
                    numeric_value=percentage,
                    is_free=False,
                    parse_errors=[],
                    parse_method="dual_rate_ad_valorem_free_reversed"
                )
        
        if ad_valorem_dual:
            percentage = float(ad_valorem_dual.group(1))
            programs_text = ad_valorem_dual.group(2) if ad_valorem_dual.group(2) else None
            programs = [p.strip() for p in programs_text.split(',')] if programs_text else []
            
            structure = {
                "percentage": percentage,
                "secondary_free_programs": programs,
                "special_rate_free": True,
                "eligibility_note_raw": ad_valorem_dual.group(0)
            }
            
            return ParsedDutyRate(
                raw_text=original_text,
                duty_type=DutyType.AD_VALOREM,
                duty_confidence=DutyConfidence.HIGH,
                structure=structure,
                numeric_value=percentage,
                is_free=False,  # Base rate is NOT free, special programs are
                parse_errors=[],
                parse_method="dual_rate_ad_valorem_free"
            )
        
        # Pattern 2: Compound with Free: "X¢/kg + Y% Free (programs)" (flexible spacing)
        compound_dual = re.search(r'(\d+\.?\d*)\s*[¢\$]?\s*/?\s*([a-z]+)\s*\+\s*(\d+\.?\d*)\s*%\s+free\s*(?:\(([^)]+)\))?', text_lower, re.IGNORECASE)
        if compound_dual:
            specific_amount = float(compound_dual.group(1))
            unit = compound_dual.group(2).lower() if len(compound_dual.groups()) > 1 else None
            percentage = float(compound_dual.group(3)) if len(compound_dual.groups()) > 2 else None
            programs_text = compound_dual.group(4) if len(compound_dual.groups()) > 3 else None
            
            unit_normalized = None
            quantity_basis = None
            if unit:
                unit_normalized = self.UNIT_NORMALIZATION.get(unit, unit)
                quantity_basis = self.QUANTITY_BASIS_MAP.get(unit_normalized, "units")
            
            programs = [p.strip() for p in programs_text.split(',')] if programs_text else []
            
            structure = {
                "components": [
                    {
                        "type": "specific",
                        "amount": specific_amount,
                        "unit": unit,
                        "unit_normalized": unit_normalized,
                        "quantity_basis": quantity_basis
                    },
                    {
                        "type": "ad_valorem",
                        "percentage": percentage
                    }
                ],
                "secondary_free_programs": programs,
                "special_rate_free": True,
                "eligibility_note_raw": compound_dual.group(0)
            }
            
            return ParsedDutyRate(
                raw_text=original_text,
                duty_type=DutyType.COMPOUND,
                duty_confidence=DutyConfidence.HIGH,
                structure=structure,
                numeric_value=None,
                is_free=False,
                parse_errors=[],
                parse_method="dual_rate_compound_free"
            )
        
        # Pattern 3: "Y¢/kg Free (programs)" or "Free (programs), Y¢/kg"
        specific_dual = re.search(r'(\d+\.?\d*)\s*[¢\$]?\s*/?\s*([a-z]+)\s+free\s*(?:\(([^)]+)\))?', text_lower, re.IGNORECASE)
        if not specific_dual:
            # Try "Free (programs), Y¢/kg"
            specific_dual = re.search(r'free\s*\(([^)]+)\)[^¢\$]*(\d+\.?\d*)\s*[¢\$]?\s*/?\s*([a-z]+)', text_lower, re.IGNORECASE)
            if not specific_dual:
                # Try "Free (programs, Y¢/kg" (incomplete paren, rate in programs list)
                specific_dual = re.search(r'free\s*\(([^,]+(?:,\s*[^,]+)*),\s*(\d+\.?\d*)\s*[¢\$]?\s*/?\s*([a-z]+)', text_lower, re.IGNORECASE)
            if specific_dual:
                programs_text = specific_dual.group(1)
                amount = float(specific_dual.group(2))
                unit = specific_dual.group(3).lower() if len(specific_dual.groups()) > 2 else None
                
                unit_normalized = None
                quantity_basis = None
                if unit:
                    unit_normalized = self.UNIT_NORMALIZATION.get(unit, unit)
                    quantity_basis = self.QUANTITY_BASIS_MAP.get(unit_normalized, "units")
                
                programs = [p.strip() for p in programs_text.split(',')] if programs_text else []
                
                structure = {
                    "amount": amount,
                    "currency": "USD" if "$" in text else None,
                    "secondary_free_programs": programs,
                    "special_rate_free": True,
                    "eligibility_note_raw": specific_dual.group(0)
                }
                
                if unit:
                    structure["unit"] = unit
                if unit_normalized:
                    structure["unit_normalized"] = unit_normalized
                if quantity_basis:
                    structure["quantity_basis"] = quantity_basis
                
                return ParsedDutyRate(
                    raw_text=original_text,
                    duty_type=DutyType.SPECIFIC,
                    duty_confidence=DutyConfidence.HIGH,
                    structure=structure,
                    numeric_value=amount,
                    is_free=False,
                    parse_errors=[],
                    parse_method="dual_rate_specific_free_reversed"
                )
        
        if specific_dual:
            amount = float(specific_dual.group(1))
            unit = specific_dual.group(2).lower() if len(specific_dual.groups()) > 1 else None
            programs_text = specific_dual.group(3) if len(specific_dual.groups()) > 2 and specific_dual.group(3) else None
            
            unit_normalized = None
            quantity_basis = None
            if unit:
                unit_normalized = self.UNIT_NORMALIZATION.get(unit, unit)
                quantity_basis = self.QUANTITY_BASIS_MAP.get(unit_normalized, "units")
            
            programs = []
            if programs_text:
                programs = [p.strip() for p in programs_text.split(',')]
            
            structure = {
                "amount": amount,
                "currency": "USD" if "$" in text else None,
                "secondary_free_programs": programs,
                "special_rate_free": True,
                "eligibility_note_raw": specific_dual.group(0)
            }
            
            if unit:
                structure["unit"] = unit
            if unit_normalized:
                structure["unit_normalized"] = unit_normalized
            if quantity_basis:
                structure["quantity_basis"] = quantity_basis
            
            return ParsedDutyRate(
                raw_text=original_text,
                duty_type=DutyType.SPECIFIC,
                duty_confidence=DutyConfidence.HIGH,
                structure=structure,
                numeric_value=amount,
                is_free=False,  # Base rate is NOT free, special programs are
                parse_errors=[],
                parse_method="dual_rate_specific_free"
            )
        
        return None
    
    def _attach_secondary_free_programs(self, result: ParsedDutyRate, secondary_lines: List[str]) -> None:
        """
        Attach secondary Free program notes to a parsed result.
        
        Checks secondary lines for "Free (A+, AU, ...)" patterns and adds
        them as metadata without changing duty_type or is_free.
        
        Handles multi-line program lists by searching the full secondary text.
        """
        if not secondary_lines:
            return
        
        # Join secondary lines for multi-line pattern matching
        secondary_text = '\n'.join(secondary_lines)
        secondary_lower = secondary_text.lower()
        
        # Check for "Free (program list)" pattern - handle multi-line parentheses
        # Use DOTALL to match across newlines, and look for closing paren
        free_program_match = re.search(r'free\s*\(([^)]*(?:\n[^)]*)*?)\)', secondary_lower, re.IGNORECASE | re.DOTALL)
        
        if free_program_match:
            programs_text = free_program_match.group(1)
            # Extract program codes (A+, AU, BH, CL, etc.) - handle newlines and commas
            programs = [p.strip() for p in re.split(r'[,\n]', programs_text) if p.strip()]
            
            if "program_rates" not in result.structure:
                result.structure["program_rates"] = {}
            result.structure["program_rates"]["Free"] = programs
            result.structure["secondary_free_programs"] = programs
            result.structure["eligibility_note_raw"] = free_program_match.group(0)
            return
        
        # Check for standalone "Free" on secondary line (without parentheses)
        for line in secondary_lines:
            line_lower = line.lower().strip()
            if re.match(r'^\s*free\.?\s*$', line_lower, re.IGNORECASE):
                # This is a secondary Free note (not primary Free duty)
                if "program_rates" not in result.structure:
                    result.structure["program_rates"] = {}
                result.structure["program_rates"]["Free"] = []  # Empty list means "Free" without program list
                result.structure["secondary_free_note"] = "Free"
                return
    
    def _parse_free_duty(self, primary_line: str, secondary_lines: List[str], original_text: str) -> Optional[ParsedDutyRate]:
        """
        Parse "Free" duty rates using two-line interpretation model.
        
        Handles three cases:
        A) True Free: "Free", "Free\nFree", "Free." → FREE, is_free=true, confidence=HIGH
        B) Free with program list: "Free (A+, AU, ...)" → FREE, is_free=true, confidence=MEDIUM
        C) Not Free but Free appears as note: handled by _attach_secondary_free_programs
        
        Args:
            primary_line: First non-empty line (primary rate expression)
            secondary_lines: Remaining lines (program notes)
            original_text: Full original text (for preservation)
        """
        primary_lower = primary_line.lower().strip()
        
        # Case A: True Free - primary line is exactly "Free" (with optional period)
        if re.match(r'^\s*free\.?\s*$', primary_lower, re.IGNORECASE):
            structure = {
                "is_free": True,
                "type": "free"
            }
            
            return ParsedDutyRate(
                raw_text=original_text,
                duty_type=DutyType.FREE,
                duty_confidence=DutyConfidence.HIGH,
                structure=structure,
                numeric_value=0.0,
                is_free=True,
                parse_errors=[],
                parse_method="free_standalone"
            )
        
        # Case B: Free with program list - "Free (A+, AU, BH, ...)"
        free_program_match = re.search(r'^\s*free\s*\(([^)]+)\)', primary_lower, re.IGNORECASE)
        if free_program_match:
            programs_text = free_program_match.group(1)
            # Extract program codes (A+, AU, BH, CL, etc.)
            programs = [p.strip() for p in programs_text.split(',')]
            
            structure = {
                "is_free": True,
                "type": "free",
                "free_programs": programs,
                "eligibility_note_raw": free_program_match.group(0)
            }
            
            # Confidence: MEDIUM because eligibility is conditional on trade programs
            return ParsedDutyRate(
                raw_text=original_text,
                duty_type=DutyType.FREE,
                duty_confidence=DutyConfidence.MEDIUM,
                structure=structure,
                numeric_value=0.0,
                is_free=True,
                parse_errors=[],
                parse_method="free_with_programs"
            )
        
        # Case: "Free\nFree" (two-line Free) - Phase 2.3: already normalized in _normalize_lines
        # But check if primary is "Free" and secondary is also "Free"
        if len(secondary_lines) > 0:
            if re.match(r'^\s*free\.?\s*$', primary_lower, re.IGNORECASE):
                second_lower = secondary_lines[0].lower().strip()
                if re.match(r'^\s*free\.?\s*$', second_lower, re.IGNORECASE):
                    structure = {
                        "is_free": True,
                        "type": "free"
                    }
                    
                    return ParsedDutyRate(
                        raw_text=original_text,
                        duty_type=DutyType.FREE,
                        duty_confidence=DutyConfidence.HIGH,
                        structure=structure,
                        numeric_value=0.0,
                        is_free=True,
                        parse_errors=[],
                        parse_method="free_two_line"
                    )
        
        # Not a Free duty
        return None
    
    def _parse_ad_valorem_duty(self, text: str) -> Optional[ParsedDutyRate]:
        """
        Parse ad valorem (percentage) duty rates.
        
        Note: This parses the primary line only. Secondary Free notes
        are attached by _attach_secondary_free_programs.
        """
        for pattern in self.AD_VALOREM_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    percentage = float(match.group(1))
                    
                    structure = {"percentage": percentage}
                    
                    # Confidence: HIGH if clear percentage pattern
                    confidence = DutyConfidence.HIGH
                    
                    return ParsedDutyRate(
                        raw_text=text,
                        duty_type=DutyType.AD_VALOREM,
                        duty_confidence=confidence,
                        structure=structure,
                        numeric_value=percentage,  # Store as-is (4.9, not 0.049)
                        is_free=False,
                        parse_errors=[],
                        parse_method="ad_valorem_pattern_match"
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse ad valorem from '{text}': {e}")
                    continue
        
        return None
    
    def _parse_specific_duty(self, text: str) -> Optional[ParsedDutyRate]:
        """
        Parse specific (per-unit) duty rates.
        
        Examples:
        - "$0.50/kg"
        - "0.50 per kg"
        - "$1.25/piece"
        
        Note: This parses the primary line only. Secondary Free notes
        are attached by _attach_secondary_free_programs.
        """
        for pattern in self.SPECIFIC_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1))
                    unit = match.group(2).lower() if len(match.groups()) > 1 and match.group(2) else None
                    
                    # Normalize unit
                    unit_normalized = None
                    quantity_basis = None
                    
                    if unit:
                        unit_normalized = self.UNIT_NORMALIZATION.get(unit, unit)  # Keep original if not in map
                        quantity_basis = self.QUANTITY_BASIS_MAP.get(unit_normalized, "units")  # Default to "units"
                    
                    structure = {
                        "amount": amount,
                        "currency": "USD" if "$" in text else None,
                    }
                    
                    if unit:
                        structure["unit"] = unit
                    if unit_normalized:
                        structure["unit_normalized"] = unit_normalized
                    if quantity_basis:
                        structure["quantity_basis"] = quantity_basis
                    
                    # Confidence: HIGH if unit is clear, MEDIUM if unit is missing/ambiguous
                    confidence = DutyConfidence.HIGH if unit_normalized else DutyConfidence.MEDIUM
                    
                    return ParsedDutyRate(
                        raw_text=text,
                        duty_type=DutyType.SPECIFIC,
                        duty_confidence=confidence,
                        structure=structure,
                        numeric_value=amount,  # Per-unit amount (not final duty)
                        is_free=False,
                        parse_errors=[] if unit_normalized else ["Unit normalization ambiguous"],
                        parse_method="specific_pattern_match"
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse specific duty from '{text}': {e}")
                    continue
        
        return None
    
    def _parse_compound_duty(self, text: str) -> Optional[ParsedDutyRate]:
        """
        Parse compound duty rates (ad valorem + specific).
        
        Examples:
        - "4.9% + $0.50/kg"
        - "4.9% and $0.50/kg"
        
        Note: This parses the primary line only. Secondary Free notes
        are attached by _attach_secondary_free_programs.
        """
        for pattern in self.COMPOUND_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    percentage = float(match.group(1))
                    amount = float(match.group(2)) if len(match.groups()) > 1 else None
                    unit = match.group(3).lower() if len(match.groups()) > 2 and match.group(3) else None
                    
                    # Build components in order found
                    components = []
                    
                    if '¢' in pattern or 'cents' in pattern:
                        # Specific first, then ad valorem
                        if amount is not None:
                            specific_component = {
                                "type": "specific",
                                "amount": amount,
                                "currency": None,  # Cents, not dollars
                            }
                            if unit:
                                specific_component["unit"] = unit
                                unit_normalized = self.UNIT_NORMALIZATION.get(unit, unit)
                                quantity_basis = self.QUANTITY_BASIS_MAP.get(unit_normalized, "units")
                                specific_component["unit_normalized"] = unit_normalized
                                specific_component["quantity_basis"] = quantity_basis
                            components.append(specific_component)
                        
                        if percentage is not None:
                            components.append({
                                "type": "ad_valorem",
                                "percentage": percentage
                            })
                    else:
                        # Ad valorem first, then specific
                        if percentage is not None:
                            components.append({
                                "type": "ad_valorem",
                                "percentage": percentage
                            })
                        
                        if amount is not None:
                            specific_component = {
                                "type": "specific",
                                "amount": amount,
                                "currency": "USD" if "$" in text else None,
                            }
                            if unit:
                                specific_component["unit"] = unit
                                unit_normalized = self.UNIT_NORMALIZATION.get(unit, unit)
                                quantity_basis = self.QUANTITY_BASIS_MAP.get(unit_normalized, "units")
                                specific_component["unit_normalized"] = unit_normalized
                                specific_component["quantity_basis"] = quantity_basis
                            components.append(specific_component)
                    
                    structure = {"components": components}
                    
                    # Confidence: HIGH if both components clear, MEDIUM if one ambiguous
                    confidence = DutyConfidence.HIGH if (amount is not None and unit) else DutyConfidence.MEDIUM
                    
                    return ParsedDutyRate(
                        raw_text=text,
                        duty_type=DutyType.COMPOUND,
                        duty_confidence=confidence,
                        structure=structure,
                        numeric_value=None,  # Cannot compute without quantity/value
                        is_free=False,
                        parse_errors=[] if (amount and unit) else ["Incomplete compound rate parsing"],
                        parse_method="compound_pattern_match"
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse compound duty from '{text}': {e}")
                    continue
        
        return None
    
    def _parse_conditional_duty(self, text: str) -> Optional[ParsedDutyRate]:
        """
        Parse conditional duty rates (references to other subheadings/notes).
        
        Examples:
        - "See subheading 1234.56.78"
        - "As provided for in Note 2"
        
        Note: This parses the primary line only. Secondary Free notes
        are attached by _attach_secondary_free_programs.
        """
        text_lower = text.lower()
        
        for pattern in self.CONDITIONAL_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                structure = {}
                
                # Extract reference type and value
                if 'subheading' in pattern:
                    reference = match.group(1) if match.groups() else None
                    structure["condition_type"] = "subheading_reference"
                    structure["reference"] = reference
                    structure["reference_type"] = "subheading"
                elif 'heading' in pattern:
                    reference = match.group(1) if match.groups() else None
                    structure["condition_type"] = "heading_reference"
                    structure["reference"] = reference
                    structure["reference_type"] = "heading"
                elif 'note' in pattern:
                    reference = match.group(1) if match.groups() else None
                    structure["condition_type"] = "note_reference"
                    structure["reference"] = reference
                    structure["reference_type"] = "note"
                else:
                    # Generic conditional
                    structure["condition_type"] = "text_reference"
                    structure["text"] = text
                
                # Confidence: MEDIUM (reference identified but not resolved)
                return ParsedDutyRate(
                    raw_text=text,
                    duty_type=DutyType.CONDITIONAL,
                    duty_confidence=DutyConfidence.MEDIUM,
                    structure=structure,
                    numeric_value=None,  # Requires resolution
                    is_free=False,
                    parse_errors=[],
                    parse_method="conditional_pattern_match"
                )
        
        return None
    
    def _parse_text_only_duty(self, text: str) -> ParsedDutyRate:
        """
        Fallback parser for text-only duties.
        
        Preserves original text when no structured pattern matches.
        """
        structure = {
            "text": text,
            "reference_type": None,
            "reference": None
        }
        
        # Try to extract any references even if pattern didn't match
        reference_match = re.search(r'(note|heading|subheading)\s+(\d+)', text.lower())
        if reference_match:
            ref_type = reference_match.group(1)
            ref_value = reference_match.group(2)
            structure["reference_type"] = ref_type
            structure["reference"] = ref_value
        
        return ParsedDutyRate(
            raw_text=text,
            duty_type=DutyType.TEXT_ONLY,
            duty_confidence=DutyConfidence.LOW,
            structure=structure,
            numeric_value=None,
            is_free=False,
            parse_errors=["No structured pattern matched"],
            parse_method="text_only_fallback"
        )
    
    def normalize_unit(self, unit: str) -> Tuple[str, str]:
        """
        Normalize unit string to standard code and infer quantity basis.
        
        Returns:
            Tuple of (normalized_unit, quantity_basis)
        """
        unit_lower = unit.lower().strip()
        normalized = self.UNIT_NORMALIZATION.get(unit_lower, unit_lower)
        basis = self.QUANTITY_BASIS_MAP.get(normalized, "units")
        return normalized, basis
