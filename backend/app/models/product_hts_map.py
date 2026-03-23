"""Product HTS map model - GAP 5 / Pinned product_hts_map"""

from sqlalchemy import Column, String, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.core.database import Base


class ProductHTSMap(Base):
    """Maps products (SKU/shipment_item) to HTS codes"""

    __tablename__ = "product_hts_map"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    hts_code = Column(String(10), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
