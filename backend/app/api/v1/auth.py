"""
Authentication API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.models.client import Client
from app.api.dependencies import get_current_user

router = APIRouter()

# Sprint 12 dev bypass - seeded test user (must match scripts/sprint12_loop.sh)
DEV_USER_SUB = "user_s12_loop_provisioned"
DEV_USER_EMAIL = "qa-sprint12-loop@example.com"
DEV_ORG_ID = "org_s12_loop"


class LoginRequest(BaseModel):
    """Login request body"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class RegisterClientRequest(BaseModel):
    """Register new client request"""
    company_name: str
    importer_number: str
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str


@router.post("/dev-token")
async def dev_token():
    """
    Dev-only: Return JWT for seeded Sprint 12 test user.
    Only available when ENVIRONMENT is development.
    Use /dev-login on frontend when NEXT_PUBLIC_DEV_AUTH=true.
    """
    env = settings.ENVIRONMENT.lower()
    if env not in ("development", "dev", "local"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    token = create_access_token(
        data={"sub": DEV_USER_SUB, "email": DEV_USER_EMAIL}
    )
    return {"access_token": token, "token_type": "bearer", "org_id": DEV_ORG_ID}


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return access token
    
    Args:
        login_data: Email and password
        db: Database session
    
    Returns:
        Access token and user info
    
    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )
    
    # Get client info
    result = await db.execute(
        select(Client).where(Client.id == user.client_id)
    )
    client = result.scalar_one_or_none()
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
            "client_id": str(user.client_id),
            "client_name": client.company_name if client else None,
        }
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_client(
    register_data: RegisterClientRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new client and admin user
    
    Args:
        register_data: Client and admin user information
        db: Database session
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If email or importer number already exists
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == register_data.admin_email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Check if importer number already exists
    result = await db.execute(
        select(Client).where(Client.importer_number == register_data.importer_number)
    )
    existing_client = result.scalar_one_or_none()
    
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Importer number already registered",
        )
    
    # Create client
    new_client = Client(
        company_name=register_data.company_name,
        importer_number=register_data.importer_number,
    )
    db.add(new_client)
    await db.flush()  # Get client ID
    
    # Create admin user
    hashed_password = get_password_hash(register_data.admin_password)
    new_user = User(
        client_id=new_client.id,
        email=register_data.admin_email,
        hashed_password=hashed_password,
        full_name=register_data.admin_full_name,
        is_admin=True,
        is_active=True,
    )
    db.add(new_user)
    
    await db.commit()
    
    return {
        "message": "Client registered successfully",
        "client_id": str(new_client.id),
    }


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user information
    
    Args:
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        User and client information
    """
    # Get client info
    result = await db.execute(
        select(Client).where(Client.id == current_user.client_id)
    )
    client = result.scalar_one_or_none()
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login,
        "client": {
            "id": str(client.id),
            "company_name": client.company_name,
            "importer_number": client.importer_number,
            "subscription_tier": client.subscription_tier,
        } if client else None
    }


