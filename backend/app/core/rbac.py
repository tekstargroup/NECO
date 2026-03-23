"""
RBAC (Role-Based Access Control) - Sprint 7

Minimal role separation for review and override operations.

Roles:
- VIEWER: read-only access
- ANALYST: can create drafts and submit for review
- REVIEWER: can accept, reject, override
"""

from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    """User roles for RBAC."""
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    REVIEWER = "REVIEWER"


class RBACService:
    """Service for RBAC enforcement."""
    
    @staticmethod
    def can_create_review(user_role: str) -> bool:
        """Check if user can create review records."""
        return user_role in [UserRole.ANALYST.value, UserRole.REVIEWER.value]
    
    @staticmethod
    def can_submit_for_review(user_role: str) -> bool:
        """Check if user can submit for review."""
        return user_role in [UserRole.ANALYST.value, UserRole.REVIEWER.value]
    
    @staticmethod
    def can_finalize_review(user_role: str) -> bool:
        """Check if user can finalize review (accept/reject)."""
        return user_role == UserRole.REVIEWER.value
    
    @staticmethod
    def can_create_override(user_role: str) -> bool:
        """Check if user can create override records."""
        return user_role == UserRole.REVIEWER.value
    
    @staticmethod
    def can_view_reviews(user_role: str) -> bool:
        """Check if user can view review records."""
        return user_role in [UserRole.VIEWER.value, UserRole.ANALYST.value, UserRole.REVIEWER.value]
    
    @staticmethod
    def validate_role(user_role: Optional[str]) -> str:
        """Validate and normalize user role."""
        if not user_role:
            return UserRole.VIEWER.value  # Default to VIEWER
        
        role_upper = user_role.upper()
        if role_upper in [r.value for r in UserRole]:
            return role_upper
        
        raise ValueError(f"Invalid role: {user_role}. Must be one of: {[r.value for r in UserRole]}")
