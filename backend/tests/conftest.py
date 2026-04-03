"""
Shared pytest fixtures for backend tests.

Provides async DB sessions for integration-style tests (e.g. classification invariants).
"""

import pytest_asyncio

from app.core.database import async_session_maker


@pytest_asyncio.fixture
async def db_session():
    """Async SQLAlchemy session; closed after each test."""
    async with async_session_maker() as session:
        yield session
