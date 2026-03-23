"""
S3 Upload Service - Sprint 12

Two-step upload: presign and confirm.
S3 key format: s3://neco/{environment}/org_{organization_id}/ship_{shipment_id}/docs/{document_type}/{uuid}.pdf
Immutability and dedupe enforced.
"""

import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
import botocore.exceptions

from app.core.config import settings
from app.models.shipment import Shipment
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.repositories.org_scoped_repository import OrgScopedRepository

logger = logging.getLogger(__name__)

# Allowed file types for shipment documents (Sprint 12.2)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "text/csv",
}

# S3 client (lazy initialization)
_s3_client = None


def get_s3_client():
    """Get or create S3 client (lazy initialization)."""
    global _s3_client
    
    if _s3_client is None:
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for S3 upload. Install with: pip install boto3")
        
        _s3_client = boto3.client(
            's3',
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL
        )
    
    return _s3_client


class S3UploadService:
    """Service for S3 presigned uploads and document confirmation"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_s3_key(
        self,
        organization_id: UUID,
        shipment_id: UUID,
        document_type: ShipmentDocumentType,
        filename: str
    ) -> str:
        """
        Generate S3 key with org and shipment encoding.
        
        Format: neco/{environment}/org_{organization_id}/ship_{shipment_id}/docs/{document_type}/{uuid}.pdf
        
        Args:
            organization_id: Organization ID
            shipment_id: Shipment ID
            document_type: Document type
            filename: Original filename (used for extension)
        
        Returns:
            S3 key string
        """
        # Extract extension from filename (default to .pdf for backwards compat)
        if '.' in filename:
            ext = filename.rsplit('.', 1)[1].lower()
            if ext not in ('pdf', 'docx', 'xlsx', 'xls', 'csv'):
                ext = 'pdf'
        else:
            ext = 'pdf'
        
        # Generate unique ID
        unique_id = str(uuid.uuid4())
        
        # Build key
        key = f"neco/{settings.ENVIRONMENT}/org_{organization_id}/ship_{shipment_id}/docs/{document_type.value}/{unique_id}.{ext}"
        
        return key
    
    async def presign_upload(
        self,
        shipment_id: UUID,
        organization_id: UUID,
        document_type: ShipmentDocumentType,
        filename: str,
        content_type: str,
        local_upload_base_url: Optional[str] = None,
        expires_in: int = 3600  # 1 hour default
    ) -> Dict[str, Any]:
        """
        Generate presigned PUT URL for S3 upload.
        
        Args:
            shipment_id: Shipment ID
            organization_id: Organization ID (for S3 key generation)
            document_type: Document type
            filename: Original filename
            content_type: Content type (must be application/pdf)
            expires_in: URL expiration in seconds (default: 1 hour)
        
        Returns:
            {
                "upload_url": str,
                "s3_key": str,
                "required_headers": dict,
                "expires_in": int
            }
        
        Raises:
            HTTPException: If content_type is not allowed
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: PDF, Word (.docx), Excel (.xlsx, .xls), CSV. Got: {content_type}"
            )
        
        # Generate S3 key
        s3_key = self._generate_s3_key(organization_id, shipment_id, document_type, filename)
        
        # Check if S3 key already exists (immutability) - optional check during presign
        # Full immutability check happens in confirm_upload via unique constraint
        # This is a pre-check to fail early
        if settings.S3_BUCKET_NAME:
            try:
                s3_client = get_s3_client()
                s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
                # Object exists - do not allow overwrite
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"S3 key already exists: {s3_key}. Immutable blobs cannot be overwritten."
                )
            except Exception as e:
                # Check if it's a "not found" error (expected for new uploads)
                error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '') if hasattr(e, 'response') else ''
                if error_code == '404' or 'NoSuchKey' in str(e):
                    # Object doesn't exist - this is expected for new uploads
                    pass
                else:
                    # Some other error - log but don't block (unique constraint will catch duplicates)
                    logger.warning(f"Error checking S3 object existence (non-blocking): {e}")
        
        # Dev/local fallback when S3 is not configured.
        # This keeps the API contract functional for QA and local pilot testing.
        # Frontend sends X-S3-Key header so mock stores at path derived from s3_key.
        if not settings.S3_BUCKET_NAME:
            if settings.ENVIRONMENT.lower() in {"development", "dev", "local"} and local_upload_base_url:
                upload_token = str(uuid.uuid4())
                base = (settings.LOCAL_UPLOAD_BASE_URL or local_upload_base_url).rstrip("/")
                upload_url = f"{base}/api/v1/shipment-documents/mock-upload/{upload_token}"
                logger.info("Presign mock upload: upload_url=%s s3_key=%s", upload_url, s3_key)
                return {
                    "upload_url": upload_url,
                    "s3_key": s3_key,
                    "required_headers": {
                        "Content-Type": content_type
                    },
                    "expires_in": expires_in
                }

            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="S3 upload is not configured for this environment (missing S3_BUCKET_NAME)"
            )
        
        s3_client = get_s3_client()
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.S3_BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=expires_in
        )
        
        return {
            "upload_url": presigned_url,
            "s3_key": s3_key,
            "required_headers": {
                "Content-Type": content_type
            },
            "expires_in": expires_in
        }
    
    async def confirm_upload(
        self,
        shipment_id: UUID,
        organization_id: UUID,
        document_type: ShipmentDocumentType,
        s3_key: str,
        sha256_hash: str,
        filename: str,
        content_type: str,
        file_size: str,
        uploaded_by: UUID
    ) -> Dict[str, Any]:
        """
        Confirm S3 upload and create ShipmentDocument record.
        
        Handles dedupe: if duplicate (shipment_id, sha256_hash), return existing document.
        
        Args:
            shipment_id: Shipment ID
            organization_id: Organization ID
            document_type: Document type
            s3_key: S3 key (from presign)
            sha256_hash: SHA256 hash of file
            filename: Original filename
            content_type: Content type (must be application/pdf)
            file_size: File size (string for flexibility)
            uploaded_by: User ID who uploaded
        
        Returns:
            {
                "document_id": str,
                "shipment_id": str,
                "is_new": bool,
                "eligibility": dict,
                "warnings": List[str]
            }
        
        Raises:
            HTTPException: If validation fails
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: PDF, Word (.docx), Excel (.xlsx, .xls), CSV. Got: {content_type}"
            )
        
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension {ext} not allowed. Allowed: .pdf, .docx, .xlsx, .xls, .csv"
            )
        
        # Validate shipment exists and belongs to org
        repo = OrgScopedRepository(self.db, Shipment)
        shipment = await repo.get_by_id(shipment_id, organization_id)
        
        # Check for duplicate (shipment_id, sha256_hash)
        result = await self.db.execute(
            select(ShipmentDocument).where(
                and_(
                    ShipmentDocument.shipment_id == shipment_id,
                    ShipmentDocument.sha256_hash == sha256_hash
                )
            )
        )
        existing_doc = result.scalar_one_or_none()
        
        if existing_doc:
            # Duplicate - return existing document
            logger.info(f"Duplicate document detected: shipment {shipment_id}, hash {sha256_hash[:16]}...")
            
            # Compute eligibility (document already existed)
            from app.services.shipment_eligibility_service import ShipmentEligibilityService
            eligibility_service = ShipmentEligibilityService(self.db)
            eligibility = await eligibility_service.compute_eligibility(shipment_id)
            
            return {
                "document_id": str(existing_doc.id),
                "shipment_id": str(shipment_id),
                "is_new": False,
                "eligibility": eligibility,
                "warnings": ["Document with this hash already exists for this shipment"]
            }
        
        # Verify S3 object exists and size matches (optional HEAD request)
        warnings = []
        if settings.S3_BUCKET_NAME:
            try:
                s3_client = get_s3_client()
                response = s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
                s3_size = str(response.get('ContentLength', 0))
                
                if s3_size != file_size:
                    warnings.append(f"S3 object size ({s3_size}) does not match provided file_size ({file_size})")
            except s3_client.exceptions.ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == '404':
                    warnings.append(f"S3 object not found at key: {s3_key}")
                else:
                    logger.warning(f"Error verifying S3 object: {e}")
        
        # Validate file_size > 0
        try:
            size_int = int(file_size) if file_size else 0
            if size_int <= 0:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="file_size must be greater than 0"
                )
        except ValueError:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_size must be numeric"
            )
        
        # Create ShipmentDocument
        retention_expires_at = datetime.utcnow() + timedelta(days=60)
        
        doc = ShipmentDocument(
            shipment_id=shipment_id,
            organization_id=organization_id,
            document_type=document_type,
            filename=filename,
            file_size=file_size,
            mime_type=content_type,
            s3_key=s3_key,
            sha256_hash=sha256_hash,
            retention_expires_at=retention_expires_at,
            uploaded_by=uploaded_by,
            processing_status="UPLOADED"
        )
        
        self.db.add(doc)
        try:
            await self.db.flush()
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            from fastapi import HTTPException, status
            message = str(e.orig) if getattr(e, "orig", None) else str(e)
            if "ix_shipment_documents_sha256_hash" in message:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Document hash already exists. Duplicate content cannot be re-registered."
                )
            if "ix_shipment_documents_s3_key" in message:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Document storage key already exists. Retry presign to get a new key."
                )
            raise
        await self.db.refresh(doc)
        
        # Compute eligibility and update shipment status
        from app.services.shipment_eligibility_service import ShipmentEligibilityService
        from app.models.shipment import ShipmentStatus
        
        eligibility_service = ShipmentEligibilityService(self.db)
        eligibility = await eligibility_service.compute_eligibility(shipment_id)
        
        # Update shipment status based on eligibility
        if eligibility["eligible"]:
            shipment.status = ShipmentStatus.READY
        else:
            shipment.status = ShipmentStatus.DRAFT
        
        await self.db.commit()
        
        # TODO: Emit event - document_uploaded_confirmed
        # events.emit("document_uploaded_confirmed", {...})
        
        return {
            "document_id": str(doc.id),
            "shipment_id": str(shipment_id),
            "is_new": True,
            "eligibility": eligibility,
            "warnings": warnings
        }
    
    async def presign_download(
        self,
        document_id: UUID,
        organization_id: UUID,
        expires_in: int = 3600  # 1 hour default
    ) -> str:
        """
        Generate presigned GET URL for document download/viewing.
        
        Args:
            document_id: Document ID
            organization_id: Organization ID (for verification)
            expires_in: URL expiration in seconds (default: 1 hour)
        
        Returns:
            Presigned download URL
        
        Raises:
            HTTPException: 404 if document not found or org mismatch
        """
        # Get document
        result = await self.db.execute(
            select(ShipmentDocument).where(ShipmentDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify org match (404 on mismatch)
        if doc.organization_id != organization_id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Generate presigned URL
        if not settings.S3_BUCKET_NAME:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3_BUCKET_NAME not configured"
            )
        
        s3_client = get_s3_client()
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.S3_BUCKET_NAME,
                'Key': doc.s3_key
            },
            ExpiresIn=expires_in
        )
        
        return presigned_url
