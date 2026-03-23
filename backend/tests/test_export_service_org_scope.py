import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.export_service import ExportService


@pytest.mark.asyncio
async def test_load_review_with_org_check_raises_value_error_when_not_found():
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)

    with patch("app.services.export_service.get_s3_client", return_value=MagicMock()):
        service = ExportService(db)

    with pytest.raises(ValueError, match="not found or access denied"):
        await service._load_review_with_org_check(uuid4(), uuid4())
