"""
Enrichment Audit Service - Sprint 10

Auditability and replayability for enrichment.

Key principles:
- Persist EnrichmentBundle snapshots
- Link to review records
- Ensure replayability
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.models.enrichment_bundle import EnrichmentBundle
from app.models.document_record import DocumentRecord

logger = logging.getLogger(__name__)


class EnrichmentAuditRecord:
    """
    Audit record for enrichment bundles.
    
    Note: This would be a SQLAlchemy model in production.
    For now, using a simple class structure.
    """
    
    def __init__(
        self,
        enrichment_id: str,
        document_id: str,
        document_hash: str,
        parser_version: str,
        enrichment_bundle: EnrichmentBundle,
        linked_review_id: Optional[str] = None,
        linked_review_type: Optional[str] = None
    ):
        self.enrichment_id = enrichment_id
        self.document_id = document_id
        self.document_hash = document_hash
        self.parser_version = parser_version
        self.enrichment_bundle = enrichment_bundle
        self.linked_review_id = linked_review_id
        self.linked_review_type = linked_review_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enrichment_id": self.enrichment_id,
            "document_id": self.document_id,
            "document_hash": self.document_hash,
            "parser_version": self.parser_version,
            "enrichment_bundle": self.enrichment_bundle.to_dict(),
            "linked_review_id": self.linked_review_id,
            "linked_review_type": self.linked_review_type
        }


class EnrichmentAuditService:
    """Service for enrichment auditability."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._audit_records: Dict[str, EnrichmentAuditRecord] = {}  # In-memory for now
    
    async def persist_enrichment_snapshot(
        self,
        enrichment_bundle: EnrichmentBundle,
        linked_review_id: Optional[str] = None,
        linked_review_type: Optional[str] = None
    ) -> str:
        """
        Persist enrichment bundle snapshot.
        
        Returns enrichment_id for reference.
        """
        import uuid
        enrichment_id = str(uuid.uuid4())
        
        audit_record = EnrichmentAuditRecord(
            enrichment_id=enrichment_id,
            document_id=enrichment_bundle.document_id,
            document_hash=enrichment_bundle.document_hash,
            parser_version=enrichment_bundle.parser_version,
            enrichment_bundle=enrichment_bundle,
            linked_review_id=linked_review_id,
            linked_review_type=linked_review_type
        )
        
        # Store (in production, would persist to database)
        self._audit_records[enrichment_id] = audit_record
        
        logger.info(f"Persisted enrichment snapshot {enrichment_id} for document {enrichment_bundle.document_id}")
        
        return enrichment_id
    
    async def replay_enrichment(
        self,
        document_hash: str,
        parser_version: str
    ) -> Optional[EnrichmentBundle]:
        """
        Replay enrichment for a document.
        
        Same document hash + same parser version = same extracted fields.
        """
        # Find document by hash
        from app.services.document_ingestion_service import DocumentIngestionService
        ingestion_service = DocumentIngestionService(self.db)
        
        # In production, would fetch document record
        # For now, return None (would need actual document record)
        
        logger.info(f"Replay requested for document hash {document_hash[:8]} with parser {parser_version}")
        
        return None
    
    async def get_enrichment_snapshot(self, enrichment_id: str) -> Optional[EnrichmentAuditRecord]:
        """Get enrichment snapshot by ID."""
        return self._audit_records.get(enrichment_id)
    
    async def get_enrichments_for_review(self, review_id: str) -> list[EnrichmentAuditRecord]:
        """Get all enrichment snapshots linked to a review."""
        return [
            record for record in self._audit_records.values()
            if record.linked_review_id == review_id
        ]
