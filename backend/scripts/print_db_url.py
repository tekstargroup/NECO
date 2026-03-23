#!/usr/bin/env python3
"""
Print DATABASE_URL from settings (masking password)
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from scripts/)
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
import re

def mask_password(url: str) -> str:
    """Mask password in database URL"""
    # Pattern: postgresql+asyncpg://user:password@host:port/db
    pattern = r'(postgresql\+?asyncpg?://[^:]+:)([^@]+)(@.+)'
    return re.sub(pattern, r'\1****\3', url)

if __name__ == "__main__":
    db_url = settings.DATABASE_URL
    print(f"DATABASE_URL: {mask_password(db_url)}")
    print(f"Has asyncpg: {'+asyncpg' in db_url}")
    print(f"Full URL (masked): {mask_password(db_url)}")

