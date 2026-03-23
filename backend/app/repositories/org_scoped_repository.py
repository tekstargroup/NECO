"""
Org-Scoped Repository - Sprint 12

Single, consistent pattern for scoping: every query requires organization_id and enforces it.
No "optional org_id" parameters.
If org mismatch, return 404 (not 403) to avoid leakage.
"""

from typing import TypeVar, Generic, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import DeclarativeBase
from fastapi import HTTPException, status

T = TypeVar("T", bound=DeclarativeBase)


class OrgScopedRepository(Generic[T]):
    """
    Base repository with organization scoping enforcement.
    
    Every query requires organization_id.
    Returns 404 (not 403) on org mismatch to avoid leakage.
    """
    
    def __init__(self, db: AsyncSession, model: type[T], org_id_field: str = "organization_id"):
        """
        Initialize org-scoped repository.
        
        Args:
            db: Database session
            model: SQLAlchemy model class
            org_id_field: Name of organization_id field in model (default: "organization_id")
        """
        self.db = db
        self.model = model
        self.org_id_field = org_id_field
    
    async def get_by_id(
        self,
        id: UUID,
        organization_id: UUID,
        raise_if_not_found: bool = True
    ) -> Optional[T]:
        """
        Get entity by ID, scoped to organization.
        
        Args:
            id: Entity ID
            organization_id: Organization ID (required)
            raise_if_not_found: Raise 404 if not found (default: True)
        
        Returns:
            Entity or None
        
        Raises:
            HTTPException: 404 if not found or org mismatch
        """
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.id == id,
                    getattr(self.model, self.org_id_field) == organization_id
                )
            )
        )
        entity = result.scalar_one_or_none()
        
        if entity is None and raise_if_not_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
        
        return entity
    
    async def list_by_org(
        self,
        organization_id: UUID,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None
    ) -> List[T]:
        """
        List entities by organization.
        
        Args:
            organization_id: Organization ID (required)
            limit: Limit results
            offset: Offset results
            order_by: Order by field (default: created_at DESC)
        
        Returns:
            List of entities
        """
        query = select(self.model).where(
            getattr(self.model, self.org_id_field) == organization_id
        )
        
        if order_by is None:
            order_by = "created_at"
        
        # Simple order by (ascending by default, prepend - for DESC)
        if order_by.startswith("-"):
            order_field = getattr(self.model, order_by[1:])
            query = query.order_by(order_field.desc())
        else:
            order_field = getattr(self.model, order_by)
            query = query.order_by(order_field.asc())
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def count_by_org(self, organization_id: UUID) -> int:
        """
        Count entities by organization.
        
        Args:
            organization_id: Organization ID (required)
        
        Returns:
            Count of entities
        """
        from sqlalchemy import func
        
        result = await self.db.execute(
            select(func.count()).select_from(
                select(self.model).where(
                    getattr(self.model, self.org_id_field) == organization_id
                ).subquery()
            )
        )
        return result.scalar_one() or 0
    
    async def create(self, entity: T) -> T:
        """
        Create entity (organization_id must be set).
        
        Args:
            entity: Entity to create
        
        Returns:
            Created entity
        """
        self.db.add(entity)
        await self.db.flush()
        return entity
    
    async def update(self, entity: T) -> T:
        """
        Update entity (organization_id must match).
        
        Args:
            entity: Entity to update
        
        Returns:
            Updated entity
        """
        await self.db.flush()
        return entity
    
    def _enforce_org_match(self, entity: T, organization_id: UUID) -> None:
        """
        Enforce organization match (internal helper).
        
        Args:
            entity: Entity to check
            organization_id: Expected organization ID
        
        Raises:
            HTTPException: 404 if org mismatch
        """
        entity_org_id = getattr(entity, self.org_id_field)
        if entity_org_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found"
            )
