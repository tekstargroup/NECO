"""
Sprint 12 API Dependencies - Clerk auth bridge with deterministic provisioning.

Posture:
- Accept Authorization: Bearer <Clerk JWT>
- When CLERK_JWT_VERIFY=true + CLERK_JWKS_URL is set: full signature, exp, iss verification
- When verification is disabled (dev): extract claims without verification + log warning on first call
- Require explicit org header: X-Clerk-Org-Id
- Default strict provisioning (no auto-creates)
- Optional dev-only auto-provision gated by env var
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from jose import jwt, jwk, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User

logger = logging.getLogger(__name__)

_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0}
_JWKS_CACHE_TTL = 3600  # re-fetch JWKS every hour
_unverified_warning_logged = False


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Authorization header missing)",
        )
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Bearer token missing)",
        )
    return token


async def _get_jwks() -> Optional[dict]:
    """Fetch and cache Clerk JWKS keys (async-safe)."""
    if not settings.CLERK_JWKS_URL:
        return None
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_CACHE_TTL:
        return _jwks_cache["keys"]
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.CLERK_JWKS_URL, timeout=10)
            resp.raise_for_status()
            keys = resp.json()
        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = now
        return keys
    except Exception as e:
        logger.error("Failed to fetch Clerk JWKS from %s: %s", settings.CLERK_JWKS_URL, e)
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        return None


async def _verify_and_decode(token: str) -> dict[str, Any]:
    """Verify JWT signature and decode claims using Clerk JWKS."""
    jwks_data = await _get_jwks()
    if not jwks_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication unavailable (JWKS not loaded)",
        )
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Invalid token header)",
        )
    kid = unverified_header.get("kid")
    matching_key = None
    for key_data in jwks_data.get("keys", []):
        if key_data.get("kid") == kid:
            matching_key = key_data
            break
    if not matching_key:
        _jwks_cache["keys"] = None
        jwks_data = await _get_jwks()
        if jwks_data:
            for key_data in jwks_data.get("keys", []):
                if key_data.get("kid") == kid:
                    matching_key = key_data
                    break
    if not matching_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (No matching signing key)",
        )
    try:
        rsa_key = jwk.construct(matching_key)
        audience = settings.CLERK_JWT_AUDIENCE or None
        decode_options = {"verify_exp": True, "verify_aud": audience is not None}
        issuer = settings.CLERK_JWT_ISSUER or None
        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options=decode_options,
            issuer=issuer,
            audience=audience,
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Token expired)",
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication required (Token verification failed: {e})",
        )


async def _extract_claims(token: str) -> dict[str, Any]:
    """Extract JWT claims — verified when configured, unverified in dev."""
    global _unverified_warning_logged
    if settings.CLERK_JWT_VERIFY and settings.CLERK_JWKS_URL:
        return await _verify_and_decode(token)
    if not _unverified_warning_logged:
        logger.warning(
            "JWT verification DISABLED (CLERK_JWT_VERIFY=%s, CLERK_JWKS_URL=%s). "
            "Set CLERK_JWT_VERIFY=true and CLERK_JWKS_URL to enable.",
            settings.CLERK_JWT_VERIFY,
            "set" if settings.CLERK_JWKS_URL else "unset",
        )
        _unverified_warning_logged = True
    try:
        return jwt.get_unverified_claims(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Invalid Clerk token)",
        )


def _is_dev_auto_provision_enabled() -> bool:
    env = settings.ENVIRONMENT.lower()
    is_dev_env = env in {"development", "dev", "local"}
    enabled = settings.SPRINT12_DEV_AUTO_PROVISION and is_dev_env

    if settings.SPRINT12_DEV_AUTO_PROVISION and not is_dev_env:
        logger.error(
            "SPRINT12_DEV_AUTO_PROVISION=true ignored because ENVIRONMENT=%s is not a dev environment",
            settings.ENVIRONMENT,
        )

    return enabled


async def get_current_user_sprint12(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_bearer_token(request)
    claims = await _extract_claims(token)
    clerk_user_id = claims.get("sub")

    if not isinstance(clerk_user_id, str) or not clerk_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Invalid Clerk token: missing sub)",
        )
    clerk_user_id = clerk_user_id.strip()

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()
    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User inactive",
            )
        return user

    if not _is_dev_auto_provision_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not provisioned",
        )

    email_claim = claims.get("email")
    if not isinstance(email_claim, str) or not email_claim.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not provisioned (dev auto-provision requires email claim)",
        )
    email = email_claim.strip().lower()
    full_name_claim = claims.get("name")
    full_name = full_name_claim.strip() if isinstance(full_name_claim, str) else None

    user = User(
        clerk_user_id=clerk_user_id,
        email=email,
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
        logger.warning("Dev auto-provisioned user for clerk_user_id=%s", clerk_user_id)
        return user
    except IntegrityError:
        # Concurrent first-login requests can race on unique constraints.
        await db.rollback()
        result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not provisioned",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User inactive",
            )
        return user


async def get_current_organization(
    x_clerk_org_id: Optional[str] = Header(None, alias="X-Clerk-Org-Id"),
    current_user: User = Depends(get_current_user_sprint12),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    if not x_clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization required (X-Clerk-Org-Id missing)",
        )

    result = await db.execute(
        select(Organization).where(Organization.clerk_org_id == x_clerk_org_id)
    )
    organization = result.scalar_one_or_none()
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied",
        )

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == organization.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied",
        )

    return organization
