"""
NECO Configuration
Next-Gen Compliance Engine
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "NECO"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str
    SQLALCHEMY_ECHO: bool = False  # Set to True for SQL query logging
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    CLERK_JWKS_URL: Optional[str] = None  # e.g. https://<your-clerk>.clerk.accounts.dev/.well-known/jwks.json
    CLERK_JWT_ISSUER: Optional[str] = None  # e.g. https://<your-clerk>.clerk.accounts.dev
    CLERK_JWT_AUDIENCE: Optional[str] = None  # Expected aud claim (e.g. your Clerk frontend API key)
    CLERK_JWT_VERIFY: bool = False  # Enable signature + expiry verification (requires CLERK_JWKS_URL)
    SPRINT12_DEV_AUTO_PROVISION: bool = False  # Explicit dev-only gate for user auto-provisioning
    ENTITLEMENT_UNLIMITED_EMAILS: str = ""  # Comma-separated emails with unlimited entitlement (e.g. testing accounts)
    SPRINT12_INLINE_ANALYSIS_DEV: bool = True  # Dev fallback when Celery worker is unavailable
    SPRINT12_SYNC_ANALYSIS_DEV: bool = True  # When True + inline, run analysis in request and return full result (so it actually completes)
    SPRINT12_FAST_ANALYSIS_DEV: bool = True  # Dev fallback to avoid long-running external engine dependencies
    SPRINT12_INSTANT_ANALYSIS_DEV: bool = False  # When True (dev only), skip pipeline and return minimal COMPLETE result immediately so UI works
    PSC_DUTY_THRESHOLD: float = 1000.0  # Min duty (USD) to run PSC Radar in fast path; set lower (e.g. 100) for more coverage
    # Rule layer mode for classification:
    # - off: disable deterministic rule layer
    # - shadow: compute rule assessment but do not alter candidate ranking
    # - enforce: compute + apply heading bias to candidate ranking
    CLASSIFICATION_RULE_MODE: str = "enforce"
    
    # Anthropic API
    ANTHROPIC_API_KEY: str

    # Congress.gov API (optional - for Tier 4 trade bills)
    CONGRESS_API_KEY: Optional[str] = None

    # CBP CROSS: XML download URL (from rulings.cbp.gov What's New) or local file path for testing
    CBP_CROSS_XML_URL: Optional[str] = None
    CBP_CROSS_LOCAL_FILE: Optional[str] = None

    # File Upload
    MAX_UPLOAD_SIZE: int = 52428800  # 50MB
    UPLOAD_DIR: Path = Path("./data/uploads")
    
    # Vector Database
    VECTOR_DB_PATH: Path = Path("./data/vector_store")
    COLLECTION_NAME: str = "neco_compliance_knowledge"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Document Processing
    CHUNK_SIZE: int = 3000
    CHUNK_OVERLAP: int = 300
    EMBEDDING_BATCH_SIZE: int = 16
    
    # OCR
    TESSERACT_CMD: Optional[str] = None  # Set if tesseract not in PATH
    
    # Local mock uploads (Sprint 12) — path fixed relative to backend root so analysis finds files regardless of CWD
    MOCK_UPLOADS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "mock_uploads"
    # When set, use this as base URL for mock upload (presign returns upload_url = {this}/api/v1/shipment-documents/mock-upload/...).
    # Use when request.base_url is wrong (e.g. behind proxy). Example: http://localhost:9001
    LOCAL_UPLOAD_BASE_URL: Optional[str] = None

    # S3 Storage (Sprint 12)
    S3_BUCKET_NAME: Optional[str] = None  # S3 bucket name
    S3_REGION: Optional[str] = "us-east-1"  # AWS region
    AWS_ACCESS_KEY_ID: Optional[str] = None  # AWS access key (optional - can use IAM role)
    AWS_SECRET_ACCESS_KEY: Optional[str] = None  # AWS secret key (optional - can use IAM role)
    S3_ENDPOINT_URL: Optional[str] = None  # Custom S3 endpoint (for LocalStack, MinIO, etc.)
    
    def model_post_init(self, __context: object) -> None:
        import logging
        _logger = logging.getLogger("neco.config")
        # Policy: only local dev machine names may boot without verified JWT.
        # Staging, production, demo, test harnesses on shared hosts, etc. must verify.
        _local_dev_envs = frozenset({"development", "dev", "local"})
        env_lower = self.ENVIRONMENT.strip().lower()
        is_local_dev = env_lower in _local_dev_envs
        if not self.CLERK_JWT_VERIFY or not self.CLERK_JWKS_URL:
            if not is_local_dev:
                raise ValueError(
                    "Externally reachable deploys require Clerk JWT verification. "
                    "Set CLERK_JWT_VERIFY=true and CLERK_JWKS_URL. "
                    "Set CLERK_JWT_ISSUER to your Clerk issuer URL; set CLERK_JWT_AUDIENCE "
                    "if your tokens include aud and you use multiple Clerk apps. "
                    f"Current ENVIRONMENT={self.ENVIRONMENT!r}. "
                    "Only ENVIRONMENT=development, dev, or local may run without verified JWTs."
                )
            _logger.warning(
                "JWT verification DISABLED (CLERK_JWT_VERIFY=%s, CLERK_JWKS_URL=%s). "
                "Acceptable only for local dev (ENVIRONMENT=development|dev|local).",
                self.CLERK_JWT_VERIFY,
                "set" if self.CLERK_JWKS_URL else "unset",
            )

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Create directories if they don't exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
settings.MOCK_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
