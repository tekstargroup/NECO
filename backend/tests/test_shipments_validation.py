import pytest

from app.api.v1.shipments import ShipmentCreateRequest, _normalize_declared_hts


def test_normalize_declared_hts_strips_dots():
    assert _normalize_declared_hts("6112.20.20.30") == "6112202030"


def test_shipment_create_rejects_declared_hts_over_10_digits():
    with pytest.raises(ValueError, match="cannot exceed 10 digits"):
        ShipmentCreateRequest(
            name="bad-hts",
            references=[],
            items=[{"label": "x", "declared_hts_code": "1234.56.78.901.23"}],
        )
