"""enable_pg_trgm_extension

Revision ID: 002
Revises: 001
Create Date: 2026-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension (required for similarity search in classification engine)
    # This is a required extension for development and production
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    # Note: We don't drop the extension in downgrade as it may be used by other parts of the system
    # If you really need to drop it, uncomment the line below
    # op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    pass
