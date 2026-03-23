"""
HTS Node Model - Sprint 5.1.5

Stores multi-level HTS hierarchy (6, 8, 10-digit codes) with authoritative duty rates
extracted from PDF, not derived from children.

This is the source of truth for parent rates used in inheritance logic.
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class HTSNode(Base):
    """
    Multi-level HTS node storing authoritative rates from PDF extraction.
    
    Stores 6-digit headings, 8-digit subheadings, and 10-digit statistical suffixes
    as separate nodes with their own duty text. This enables proper inheritance
    (fallback to parent text) rather than statistical inference (aggregating children).
    
    Sprint 5.1.5: Hierarchy persistence using already extracted nodes.
    """
    
    __tablename__ = "hts_nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hts_version_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # FK to hts_versions (if versioned)
    code_normalized = Column(String(10), nullable=False, index=True)  # Digits only, e.g., "8518301000"
    code_display = Column(String(20), nullable=True)  # With dots, e.g., "8518.30.10.00"
    level = Column(Integer, nullable=False, index=True)  # 6, 8, or 10
    parent_code_normalized = Column(String(10), nullable=True, index=True)  # Parent node code
    description_short = Column(Text, nullable=True)  # Short description
    description_long = Column(Text, nullable=True)  # Full tariff text
    duty_general_raw = Column(Text, nullable=True)  # Raw General duty text
    duty_special_raw = Column(Text, nullable=True)  # Raw Special duty text
    duty_column2_raw = Column(Text, nullable=True)  # Raw Column 2 duty text
    source_lineage = Column(JSONB, nullable=True)  # Page, line, offsets if available
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_hts_nodes_parent', parent_code_normalized, level),
        Index('idx_hts_nodes_code_level', code_normalized, level),
    )
    
    def __repr__(self):
        return f"<HTSNode {self.code_display or self.code_normalized} (level {self.level})>"
