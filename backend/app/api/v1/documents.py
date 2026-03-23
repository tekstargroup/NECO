"""
Document Upload and Processing API
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import shutil
from datetime import datetime
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.client import Client
from app.models.document import Document, DocumentType, ProcessingStatus
from app.api.dependencies import get_current_user, get_current_client
from app.engines.ingestion import DocumentProcessor

router = APIRouter()

# Initialize document processor
doc_processor = DocumentProcessor()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and process a document
    
    Args:
        file: Uploaded file
        current_user: Current authenticated user
        current_client: Current client
        db: Database session
    
    Returns:
        Upload status and document ID
    """
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
        )
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    allowed_extensions = [".pdf", ".xlsx", ".xls", ".csv"]
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create client-specific upload directory
    client_upload_dir = settings.UPLOAD_DIR / str(current_client.id)
    client_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = client_upload_dir / safe_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving file: {str(e)}"
        )
    
    # Create document record
    document = Document(
        client_id=current_client.id,
        filename=file.filename,
        file_path=str(file_path),
        file_size=file_size,
        mime_type=file.content_type,
        processing_status=ProcessingStatus.UPLOADED,
        uploaded_by=current_user.id,
    )
    
    db.add(document)
    await db.flush()
    
    # Process document
    try:
        document.processing_status = ProcessingStatus.PROCESSING
        document.processing_started_at = datetime.utcnow()
        await db.commit()
        
        # Run processing
        processing_start = datetime.utcnow()
        result = doc_processor.process_document(file_path)
        processing_end = datetime.utcnow()
        
        # Update document with results
        if result["success"]:
            document.processing_status = ProcessingStatus.COMPLETED
            document.document_type = DocumentType(result.get("document_type", "other"))
            document.extracted_text = result.get("extracted_text", "")
            document.structured_data = result.get("structured_data")
            document.confidence_score = result.get("confidence_score", 0)
            document.processing_completed_at = processing_end
            document.processing_duration_seconds = int((processing_end - processing_start).total_seconds())
            
            # Extract PO number if available
            if document.structured_data:
                document.po_number = document.structured_data.get("po_number")
        else:
            document.processing_status = ProcessingStatus.FAILED
            document.processing_error = result.get("error", "Unknown error")
        
        await db.commit()
    
    except Exception as e:
        document.processing_status = ProcessingStatus.FAILED
        document.processing_error = str(e)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )
    
    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "confidence_score": document.confidence_score,
        "structured_data": document.structured_data,
        "message": "Document uploaded and processed successfully"
    }


@router.get("/documents")
async def list_documents(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    """
    List all documents for current client
    
    Args:
        current_client: Current client
        db: Database session
    
    Returns:
        List of documents
    """
    from sqlalchemy import select, desc
    
    result = await db.execute(
        select(Document)
        .where(Document.client_id == current_client.id)
        .order_by(desc(Document.uploaded_at))
        .limit(100)
    )
    
    documents = result.scalars().all()
    
    return {
        "documents": [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "document_type": doc.document_type,
                "processing_status": doc.processing_status,
                "file_size": doc.file_size,
                "uploaded_at": doc.uploaded_at,
                "confidence_score": doc.confidence_score,
                "po_number": doc.po_number,
            }
            for doc in documents
        ],
        "total": len(documents)
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Get document details
    
    Args:
        document_id: Document ID
        current_client: Current client
        db: Database session
    
    Returns:
        Document details
    """
    from sqlalchemy import select
    from uuid import UUID
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    
    result = await db.execute(
        select(Document).where(
            Document.id == doc_uuid,
            Document.client_id == current_client.id
        )
    )
    
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return {
        "id": str(document.id),
        "filename": document.filename,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "file_size": document.file_size,
        "uploaded_at": document.uploaded_at,
        "confidence_score": document.confidence_score,
        "po_number": document.po_number,
        "structured_data": document.structured_data,
        "extracted_text": document.extracted_text[:1000] if document.extracted_text else None,  # Preview only
        "processing_duration_seconds": document.processing_duration_seconds,
        "processing_error": document.processing_error,
    }


