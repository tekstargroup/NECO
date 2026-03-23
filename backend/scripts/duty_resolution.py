"""
Duty Resolution Contract - Sprint 5.3

Defines the ResolvedDuty data structure for duty inheritance resolution.
Each duty field (general, special, column2) resolves independently.

Sprint 5.3 Step 2: Deterministic Inheritance Resolver
- Walks tree upward: 10-digit → 8-digit → 6-digit → chapter
- Resolves each duty field independently
- Records inheritance path
- Flags missing duties

Sprint 5.3 Step 4: Database Integration
- Wires resolver to actual HTSNode table
- Ensures normalization matches extractor output exactly
"""

from dataclasses import dataclass, field
from typing import Optional, List, Literal, Dict, Callable, Any, TYPE_CHECKING
from enum import Enum
import re

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.hts_node import HTSNode


class DutySourceLevel(str, Enum):
    """Source level for duty resolution."""
    LEVEL_10 = "10"
    LEVEL_8 = "8"
    LEVEL_6 = "6"
    CHAPTER = "chapter"
    NONE = "none"


class DutyFlag(str, Enum):
    """Flags for duty resolution status."""
    INHERITED_FROM_PARENT = "INHERITED_FROM_PARENT"
    MISSING_DUTY = "MISSING_DUTY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass
class ResolvedDuty:
    """
    Resolved duty information for a single HTS code.
    
    Each duty field (general, special, column2) resolves independently.
    The inheritance_path tracks the ordered list of HTS codes checked during resolution.
    """
    hts_code: str
    
    # Resolved duty values (may be None if not found)
    resolved_general_raw: Optional[str] = None
    resolved_special_raw: Optional[str] = None
    resolved_col2_raw: Optional[str] = None
    
    # Source level for each duty field
    source_level_general: Literal["10", "8", "6", "chapter", "none"] = "none"
    source_level_special: Literal["10", "8", "6", "chapter", "none"] = "none"
    source_level_col2: Literal["10", "8", "6", "chapter", "none"] = "none"
    
    # Source HTS code for each duty field (the code where duty was found)
    source_hts_general: Optional[str] = None
    source_hts_special: Optional[str] = None
    source_hts_col2: Optional[str] = None
    
    # Ordered list of HTS codes checked during resolution (from child to ancestor)
    inheritance_path: List[str] = field(default_factory=list)
    
    # Flags indicating resolution status
    flags: List[DutyFlag] = field(default_factory=list)
    
    # Explanations (built from resolver metadata)
    explanation_general: Optional[str] = None
    explanation_special: Optional[str] = None
    explanation_col2: Optional[str] = None
    explanation_path: Optional[str] = None
    
    def add_flag(self, flag: DutyFlag) -> None:
        """Add a flag if not already present."""
        if flag not in self.flags:
            self.flags.append(flag)
    
    def has_flag(self, flag: DutyFlag) -> bool:
        """Check if a flag is present."""
        return flag in self.flags
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "hts_code": self.hts_code,
            "resolved_general_raw": self.resolved_general_raw,
            "resolved_special_raw": self.resolved_special_raw,
            "resolved_col2_raw": self.resolved_col2_raw,
            "source_level_general": self.source_level_general,
            "source_level_special": self.source_level_special,
            "source_level_col2": self.source_level_col2,
            "source_hts_general": self.source_hts_general,
            "source_hts_special": self.source_hts_special,
            "source_hts_col2": self.source_hts_col2,
            "inheritance_path": self.inheritance_path,
            "flags": [flag.value for flag in self.flags],
            "explanation_general": self.explanation_general,
            "explanation_special": self.explanation_special,
            "explanation_col2": self.explanation_col2,
            "explanation_path": self.explanation_path,
        }


def normalize_hts_code(code: str) -> str:
    """
    Normalize HTS code to digits only (remove dots, spaces).
    
    Matches extractor normalization exactly (regenerate_structured_hts_codes_v2.py).
    """
    if not code:
        return ""
    normalized = re.sub(r'[^\d]', '', code)
    # INVARIANT: Must be valid length (matches extractor validation)
    if normalized and len(normalized) not in [6, 8, 10]:
        raise ValueError(f"Normalized code '{normalized}' has invalid length {len(normalized)}")
    return normalized


def get_parent_code(code_normalized: str, target_level: int) -> Optional[str]:
    """Get parent code at target level (6 or 8 digits)."""
    if len(code_normalized) < target_level:
        return None
    return code_normalized[:target_level]


def determine_level(code_normalized: str) -> int:
    """Determine HTS code level from length."""
    if len(code_normalized) == 10:
        return 10
    elif len(code_normalized) == 8:
        return 8
    elif len(code_normalized) == 6:
        return 6
    return 0


def level_to_source_level(level: int) -> Literal["10", "8", "6", "chapter", "none"]:
    """Convert numeric level to source_level string."""
    if level == 10:
        return "10"
    elif level == 8:
        return "8"
    elif level == 6:
        return "6"
    elif level == 0:
        return "chapter"
    return "none"


# Type alias for node fetcher function
# Returns node dict with: code_normalized, level, duty_general_raw, duty_special_raw, duty_column2_raw, parent_code_normalized
NodeFetcher = Callable[[str, int], Optional[Dict[str, Any]]]


def resolve_duty_inheritance(
    hts_code: str,
    node_fetcher: NodeFetcher
) -> ResolvedDuty:
    """
    Deterministic duty inheritance resolver.
    
    Walks the HTS tree upward (10-digit -> 8-digit -> 6-digit -> chapter) to resolve
    duty fields independently. Records full inheritance path and source tracking.
    
    Args:
        hts_code: HTS code (normalized or display format, will be normalized)
        node_fetcher: Function(code_normalized: str, level: int) -> Optional[Dict] 
                     Returns node dict with duty fields or None if not found
    
    Returns:
        ResolvedDuty object with resolved duties and full source tracking
    
    Algorithm:
        1. Normalize input code
        2. Build inheritance_path by walking parent links
        3. For each duty field (general, special, col2):
           - Iterate nodes in inheritance_path order
           - Use first non-null value found
           - Set source_level and source_hts
           - Add INHERITED_FROM_PARENT flag if not from starting node
           - Add MISSING_DUTY and REVIEW_REQUIRED if not found
    """
    # Normalize input code
    code_normalized = normalize_hts_code(hts_code)
    if not code_normalized or len(code_normalized) not in [6, 8, 10]:
        raise ValueError(f"Invalid HTS code: {hts_code} (normalized: {code_normalized})")
    
    # Initialize result
    result = ResolvedDuty(hts_code=code_normalized)
    
    # Step 1: Build inheritance_path by walking parent links
    inheritance_path = []
    current_code = code_normalized
    current_level = determine_level(current_code)
    
    # Walk upward: 10 -> 8 -> 6 -> chapter
    while current_level > 0:
        # Fetch current node
        node = node_fetcher(current_code, current_level)
        if node:
            inheritance_path.append({
                "code_normalized": node.get("code_normalized", current_code),
                "level": node.get("level", current_level),
                "duty_general_raw": node.get("duty_general_raw"),
                "duty_special_raw": node.get("duty_special_raw"),
                "duty_column2_raw": node.get("duty_column2_raw"),
            })
        else:
            # Node not found, but still record in path
            inheritance_path.append({
                "code_normalized": current_code,
                "level": current_level,
                "duty_general_raw": None,
                "duty_special_raw": None,
                "duty_column2_raw": None,
            })
        
        # Move to parent
        if current_level == 10:
            current_code = get_parent_code(current_code, 8)
            current_level = 8
        elif current_level == 8:
            current_code = get_parent_code(current_code, 6)
            current_level = 6
        elif current_level == 6:
            # Reached chapter level (6-digit is typically top-level heading)
            break
        else:
            break
    
    # Store inheritance_path as list of codes (for serialization)
    result.inheritance_path = [node["code_normalized"] for node in inheritance_path]
    
    # Step 2: Resolve each duty field independently
    starting_code = code_normalized
    
    # Resolve general duty
    for node in inheritance_path:
        if node["duty_general_raw"]:
            result.resolved_general_raw = node["duty_general_raw"]
            result.source_level_general = level_to_source_level(node["level"])
            result.source_hts_general = node["code_normalized"]
            if node["code_normalized"] != starting_code:
                result.add_flag(DutyFlag.INHERITED_FROM_PARENT)
            break
    
    if not result.resolved_general_raw:
        result.source_level_general = "none"
        result.add_flag(DutyFlag.MISSING_DUTY)
        # If we checked through 6-digit level and still missing, mark REVIEW_REQUIRED
        # Check if any node in path is 6-digit level
        has_6_digit = any(node.get("level") == 6 for node in inheritance_path)
        if has_6_digit:
            result.add_flag(DutyFlag.REVIEW_REQUIRED)
    
    # Resolve special duty
    for node in inheritance_path:
        if node["duty_special_raw"]:
            result.resolved_special_raw = node["duty_special_raw"]
            result.source_level_special = level_to_source_level(node["level"])
            result.source_hts_special = node["code_normalized"]
            if node["code_normalized"] != starting_code:
                result.add_flag(DutyFlag.INHERITED_FROM_PARENT)
            break
    
    if not result.resolved_special_raw:
        result.source_level_special = "none"
        result.add_flag(DutyFlag.MISSING_DUTY)
        # If we checked through 6-digit level and still missing, mark REVIEW_REQUIRED
        # Check if any node in path is 6-digit level
        has_6_digit = any(node.get("level") == 6 for node in inheritance_path)
        if has_6_digit:
            result.add_flag(DutyFlag.REVIEW_REQUIRED)
    
    # Resolve column2 duty
    for node in inheritance_path:
        if node["duty_column2_raw"]:
            result.resolved_col2_raw = node["duty_column2_raw"]
            result.source_level_col2 = level_to_source_level(node["level"])
            result.source_hts_col2 = node["code_normalized"]
            if node["code_normalized"] != starting_code:
                result.add_flag(DutyFlag.INHERITED_FROM_PARENT)
            break
    
    if not result.resolved_col2_raw:
        result.source_level_col2 = "none"
        result.add_flag(DutyFlag.MISSING_DUTY)
        # If we checked through 6-digit level and still missing, mark REVIEW_REQUIRED
        # Check if any node in path is 6-digit level
        has_6_digit = any(node.get("level") == 6 for node in inheritance_path)
        if has_6_digit:
            result.add_flag(DutyFlag.REVIEW_REQUIRED)
    
    # Deduplicate flags (REVIEW_REQUIRED might be added multiple times)
    result.flags = list(set(result.flags))
    
    # Step 3: Build explanations from resolver metadata
    # Pass inheritance_path nodes for provenance checking
    build_explanations(result, inheritance_path)
    
    return result


def build_explanations(resolved: ResolvedDuty, inheritance_path_nodes: List[Dict[str, Any]]) -> None:
    """
    Build broker-readable explanations for each duty field based strictly on resolver metadata.
    
    Distinguishes between "defined at" (true source) and "attached at" (carried forward during extraction).
    
    Args:
        resolved: ResolvedDuty object to populate explanations
        inheritance_path_nodes: List of node dicts from inheritance path (for provenance checking)
    """
    hts_code_display = format_hts_code_display(resolved.hts_code)
    
    # Helper: Check if duty value matches parent (for optional note, not for claims)
    def value_matches_parent(node_field_name: str, resolved_value: str) -> bool:
        """
        Check if duty value matches parent value (for informational note only).
        Does NOT indicate carry-forward without provenance tracking.
        
        Args:
            node_field_name: Field name in node dict (e.g., "duty_general_raw")
            resolved_value: Resolved duty value
        """
        if not resolved_value:
            return False
        
        # Check if any parent has same value
        for node in inheritance_path_nodes:
            if node["code_normalized"] != resolved.hts_code:
                # This is a parent node
                parent_value = node.get(node_field_name)
                if parent_value == resolved_value:
                    return True
        return False
    
    # Build explanation for general duty
    if resolved.resolved_general_raw:
        if resolved.source_hts_general == resolved.hts_code:
            # Present on starting node
            source_display = format_hts_code_display(resolved.source_hts_general)
            explanation = (
                f"General duty is {resolved.resolved_general_raw}, "
                f"present on {source_display} ({resolved.source_level_general}-digit record)."
            )
            # Optionally note if value matches parent (informational only)
            if value_matches_parent("duty_general_raw", resolved.resolved_general_raw):
                explanation += " This value matches the parent rate."
            resolved.explanation_general = explanation
        else:
            # Inherited from parent
            source_display = format_hts_code_display(resolved.source_hts_general)
            resolved.explanation_general = (
                f"General duty is {resolved.resolved_general_raw}, "
                f"inherited from {source_display} ({resolved.source_level_general}-digit level) "
                f"to {hts_code_display}."
            )
    else:
        # Missing duty - check if we reached 6-digit level
        if len(inheritance_path_nodes) >= 3:  # 10 -> 8 -> 6
            resolved.explanation_general = (
                f"General duty not found in the inheritance chain for {hts_code_display} "
                f"(checked through 6-digit level). Review required."
            )
        else:
            resolved.explanation_general = (
                f"General duty not found in the inheritance chain for {hts_code_display}. Review required."
            )
    
    # Build explanation for special duty (preserve raw format)
    if resolved.resolved_special_raw:
        if resolved.source_hts_special == resolved.hts_code:
            # Present on starting node
            source_display = format_hts_code_display(resolved.source_hts_special)
            explanation = (
                f"Special duty is {resolved.resolved_special_raw}, "
                f"present on {source_display} ({resolved.source_level_special}-digit record)."
            )
            # Optionally note if value matches parent (informational only)
            if value_matches_parent("duty_special_raw", resolved.resolved_special_raw):
                explanation += " This value matches the parent rate."
            resolved.explanation_special = explanation
        else:
            # Inherited from parent
            source_display = format_hts_code_display(resolved.source_hts_special)
            resolved.explanation_special = (
                f"Special duty is {resolved.resolved_special_raw}, "
                f"inherited from {source_display} ({resolved.source_level_special}-digit level) "
                f"to {hts_code_display}."
            )
    else:
        # Missing duty - check if we reached 6-digit level
        if len(inheritance_path_nodes) >= 3:  # 10 -> 8 -> 6
            resolved.explanation_special = (
                f"Special duty not found in the inheritance chain for {hts_code_display} "
                f"(checked through 6-digit level). Review required."
            )
        else:
            resolved.explanation_special = (
                f"Special duty not found in the inheritance chain for {hts_code_display}. Review required."
            )
    
    # Build explanation for column2 duty
    if resolved.resolved_col2_raw:
        if resolved.source_hts_col2 == resolved.hts_code:
            # Present on starting node
            source_display = format_hts_code_display(resolved.source_hts_col2)
            explanation = (
                f"Column 2 duty is {resolved.resolved_col2_raw}, "
                f"present on {source_display} ({resolved.source_level_col2}-digit record)."
            )
            # Optionally note if value matches parent (informational only)
            if value_matches_parent("duty_column2_raw", resolved.resolved_col2_raw):
                explanation += " This value matches the parent rate."
            resolved.explanation_col2 = explanation
        else:
            # Inherited from parent
            source_display = format_hts_code_display(resolved.source_hts_col2)
            resolved.explanation_col2 = (
                f"Column 2 duty is {resolved.resolved_col2_raw}, "
                f"inherited from {source_display} ({resolved.source_level_col2}-digit level) "
                f"to {hts_code_display}."
            )
    else:
        # Missing duty - check if we reached 6-digit level
        if len(inheritance_path_nodes) >= 3:  # 10 -> 8 -> 6
            resolved.explanation_col2 = (
                f"Column 2 duty not found in the inheritance chain for {hts_code_display} "
                f"(checked through 6-digit level). Review required."
            )
        else:
            resolved.explanation_col2 = (
                f"Column 2 duty not found in the inheritance chain for {hts_code_display}. Review required."
            )
    
    # Build compact path explanation (optional, short)
    if resolved.inheritance_path:
        path_display = [format_hts_code_display(code) for code in resolved.inheritance_path]
        resolved.explanation_path = f"Checked: {' → '.join(path_display)}"


def format_hts_code_display(code_normalized: str) -> str:
    """
    Format normalized HTS code to display format with dots.
    
    Examples:
        "6112201010" -> "6112.20.10.10"
        "61122010" -> "6112.20.10"
        "611220" -> "6112.20"
    """
    if not code_normalized or len(code_normalized) < 6:
        return code_normalized
    
    # Insert dots at standard positions: XXXX.XX.XX.XX
    if len(code_normalized) == 10:
        return f"{code_normalized[:4]}.{code_normalized[4:6]}.{code_normalized[6:8]}.{code_normalized[8:10]}"
    elif len(code_normalized) == 8:
        return f"{code_normalized[:4]}.{code_normalized[4:6]}.{code_normalized[6:8]}"
    elif len(code_normalized) == 6:
        return f"{code_normalized[:4]}.{code_normalized[4:6]}"
    else:
        return code_normalized


# Database integration functions

async def fetch_hts_node(
    db: "AsyncSession",
    code_normalized: str,
    level: int
) -> Optional[Dict[str, Any]]:
    """
    Fetch HTS node from database by normalized code and level.
    
    Args:
        db: Database session
        code_normalized: Normalized HTS code (digits only)
        level: Node level (6, 8, or 10)
    
    Returns:
        Node dict with duty fields or None if not found
    """
    from sqlalchemy import select
    from app.models.hts_node import HTSNode
    
    query = select(HTSNode).where(
        HTSNode.code_normalized == code_normalized,
        HTSNode.level == level
    )
    # Filter out invalid nodes (bogus synthetic codes)
    # Check if source_lineage has is_valid flag
    # For now, we'll filter in Python after fetching, but ideally should be in SQL
    result = await db.execute(query)
    node = result.scalar_one_or_none()
    
    if not node:
        return None
    
    # Filter out invalid nodes (bogus synthetic codes)
    if node.source_lineage and node.source_lineage.get("is_valid") is False:
        return None
    
    return {
        "code_normalized": node.code_normalized,
        "level": node.level,
        "duty_general_raw": node.duty_general_raw,
        "duty_special_raw": node.duty_special_raw,
        "duty_column2_raw": node.duty_column2_raw,
        "parent_code_normalized": node.parent_code_normalized,
    }


async def resolve_duty(
    hts_code: str,
    db: "AsyncSession",
    hts_version_id: Optional[str] = None
) -> ResolvedDuty:
    """
    Resolve duty inheritance for an HTS code using database.
    
    This is the main entry point for duty resolution with database integration.
    
    Args:
        hts_code: HTS code (normalized or display format)
        db: Database session
        hts_version_id: Optional HTS version ID (defaults to AUTHORITATIVE_HTS_VERSION_ID)
    
    Returns:
        ResolvedDuty object with resolved duties, source tracking, and explanations
    
    Raises:
        ValueError: If hts_version_id is provided but not recognized
    
    Example:
        async with async_session_maker() as db:
            resolved = await resolve_duty("6112.20.20.30", db)
            print(resolved.explanation_general)
    """
    from app.core.hts_constants import validate_hts_version_id
    
    # Validate and set default version
    hts_version_id = validate_hts_version_id(hts_version_id)
    from sqlalchemy import select
    from app.models.hts_node import HTSNode
    
    # Normalize input code (matches extractor normalization exactly)
    code_normalized = normalize_hts_code(hts_code)
    
    # Pre-fetch all nodes in the inheritance path (10 -> 8 -> 6)
    # This allows us to use the synchronous resolver with cached data
    nodes_cache = {}
    current_code = code_normalized
    current_level = determine_level(current_code)
    
    # Fetch nodes in inheritance path
    while current_level > 0:
        # Build query for current code and level
        query = select(HTSNode).where(
            HTSNode.code_normalized == current_code,
            HTSNode.level == current_level
        )
        if hts_version_id:
            query = query.where(HTSNode.hts_version_id == hts_version_id)
        else:
            query = query.where(HTSNode.hts_version_id.is_(None))
        
        result = await db.execute(query)
        node = result.scalar_one_or_none()
        
        if node:
            # Filter out invalid nodes (bogus synthetic codes)
            if node.source_lineage and node.source_lineage.get("is_valid") is False:
                # Skip invalid node, continue to parent
                pass
            else:
                nodes_cache[(node.code_normalized, node.level)] = {
                    "code_normalized": node.code_normalized,
                    "level": node.level,
                    "duty_general_raw": node.duty_general_raw,
                    "duty_special_raw": node.duty_special_raw,
                    "duty_column2_raw": node.duty_column2_raw,
                    "parent_code_normalized": node.parent_code_normalized,
                }
        
        # Move to parent (walk tree upward)
        if current_level == 10:
            current_code = get_parent_code(current_code, 8)
            current_level = 8
        elif current_level == 8:
            current_code = get_parent_code(current_code, 6)
            current_level = 6
        elif current_level == 6:
            # Reached chapter level (6-digit is typically top-level heading)
            # Stop here - no chapter-level lookup
            break
        else:
            break
    
    # Create sync fetcher from cache
    def sync_fetcher(code_normalized: str, level: int) -> Optional[Dict[str, Any]]:
        return nodes_cache.get((code_normalized, level))
    
    # Call resolver
    return resolve_duty_inheritance(hts_code, sync_fetcher)
