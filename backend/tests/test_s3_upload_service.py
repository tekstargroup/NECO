import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.shipment_document import ShipmentDocumentType
from app.services.s3_upload_service import S3UploadService


@pytest.mark.asyncio
async def test_presign_upload_uses_local_mock_when_s3_not_configured(monkeypatch):
    service = S3UploadService(MagicMock())
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    result = await service.presign_upload(
        shipment_id=uuid4(),
        organization_id=uuid4(),
        document_type=ShipmentDocumentType.COMMERCIAL_INVOICE,
        filename="invoice.pdf",
        content_type="application/pdf",
        local_upload_base_url="http://localhost:9001",
    )

    assert result["upload_url"].startswith("http://localhost:9001/api/v1/shipment-documents/mock-upload/")
    assert result["s3_key"].startswith("neco/development/")


@pytest.mark.asyncio
async def test_presign_upload_returns_422_without_s3_or_local_base(monkeypatch):
    service = S3UploadService(MagicMock())
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    with pytest.raises(HTTPException) as exc:
        await service.presign_upload(
            shipment_id=uuid4(),
            organization_id=uuid4(),
            document_type=ShipmentDocumentType.COMMERCIAL_INVOICE,
            filename="invoice.pdf",
            content_type="application/pdf",
            local_upload_base_url=None,
        )

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_confirm_upload_returns_409_on_sha256_conflict(monkeypatch):
    class DummyResult:
        def scalar_one_or_none(self):
            return None

    class DummyDb:
        def __init__(self):
            self.execute = AsyncMock(return_value=DummyResult())
            self.flush = AsyncMock(
                side_effect=IntegrityError(
                    statement="INSERT ...",
                    params={},
                    orig=Exception("duplicate key value violates unique constraint \"ix_shipment_documents_sha256_hash\""),
                )
            )
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.add = MagicMock()
            self.refresh = AsyncMock()

    dummy_db = DummyDb()
    service = S3UploadService(dummy_db)

    monkeypatch.setattr(settings, "S3_BUCKET_NAME", None)

    async def fake_get_by_id(self, shipment_id, organization_id):
        return type("ShipmentObj", (), {"id": shipment_id, "organization_id": organization_id})()

    monkeypatch.setattr(
        "app.services.s3_upload_service.OrgScopedRepository.get_by_id",
        fake_get_by_id,
    )

    with pytest.raises(HTTPException) as exc:
        await service.confirm_upload(
            shipment_id=uuid4(),
            organization_id=uuid4(),
            document_type=ShipmentDocumentType.COMMERCIAL_INVOICE,
            s3_key="neco/development/mock/doc.pdf",
            sha256_hash="a" * 64,
            filename="doc.pdf",
            content_type="application/pdf",
            file_size="123",
            uploaded_by=uuid4(),
        )

    assert exc.value.status_code == 409
