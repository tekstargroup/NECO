"""
Seed org/user/membership/entitlement for Sprint 12 dev login.

Same data as `seed_test_data()` in scripts/sprint12_loop.sh, but uses
backend DATABASE_URL (no Docker `exec`). Idempotent.

Run from backend/:
  source venv/bin/activate
  python scripts/seed_sprint12_dev_login.py

Must stay in sync with:
  - backend/app/api/v1/auth.py (DEV_USER_SUB, DEV_ORG_ID)
  - scripts/sprint12_loop.sh (LOOP_* constants)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

LOOP_ORG_ID = "org_s12_loop"
LOOP_ORG_NAME = "Sprint 12 Loop Org"
LOOP_ORG_SLUG = "s12-loop-org"
LOOP_USER_SUB = "user_s12_loop_provisioned"
LOOP_USER_EMAIL = "qa-sprint12-loop@example.com"
LOOP_USER_NAME = "Sprint12 Loop User"

# One statement per execute (asyncpg dislikes multiple commands in one round-trip).
SEED_STEPS: list[tuple[str, dict]] = [
    (
        """
INSERT INTO organizations (clerk_org_id, name, slug)
VALUES (:org_id, :org_name, :org_slug)
ON CONFLICT (clerk_org_id) DO UPDATE SET name = EXCLUDED.name
""",
        {
            "org_id": LOOP_ORG_ID,
            "org_name": LOOP_ORG_NAME,
            "org_slug": LOOP_ORG_SLUG,
        },
    ),
    (
        """
INSERT INTO users (id, clerk_user_id, email, full_name, is_active, is_admin, created_at)
VALUES (
  (
    substr(md5(:user_sub),1,8) || '-' ||
    substr(md5(:user_sub),9,4) || '-' ||
    substr(md5(:user_sub),13,4) || '-' ||
    substr(md5(:user_sub),17,4) || '-' ||
    substr(md5(:user_sub),21,12)
  )::uuid,
  :user_sub,
  :user_email,
  :user_name,
  true,
  false,
  now()
)
ON CONFLICT (clerk_user_id) DO UPDATE SET
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  is_active = true
""",
        {
            "user_sub": LOOP_USER_SUB,
            "user_email": LOOP_USER_EMAIL,
            "user_name": LOOP_USER_NAME,
        },
    ),
    (
        """
INSERT INTO memberships (user_id, organization_id, role, created_at)
SELECT u.id, o.id, 'ADMIN'::userrole, now()
FROM users u
JOIN organizations o ON o.clerk_org_id = :org_id
WHERE u.clerk_user_id = :user_sub
ON CONFLICT (user_id, organization_id) DO NOTHING
""",
        {"org_id": LOOP_ORG_ID, "user_sub": LOOP_USER_SUB},
    ),
    (
        """
INSERT INTO entitlements (user_id, period_start, shipments_used, shipments_limit, created_at)
SELECT
  u.id,
  date_trunc('month', timezone('America/New_York', now()))::date,
  0,
  15,
  now()
FROM users u
WHERE u.clerk_user_id = :user_sub
ON CONFLICT (user_id, period_start) DO UPDATE SET
  shipments_used = 0,
  shipments_limit = 15
""",
        {"user_sub": LOOP_USER_SUB},
    ),
]


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        for sql, params in SEED_STEPS:
            await conn.execute(text(sql), params)
    await engine.dispose()
    print(
        f"OK: seeded dev login user {LOOP_USER_SUB!r} and org {LOOP_ORG_ID!r} "
        "(idempotent)."
    )


if __name__ == "__main__":
    asyncio.run(main())
