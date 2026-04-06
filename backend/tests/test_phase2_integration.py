"""
DB-backed Phase 2 tests (optional).

Set ``RUN_PHASE2_PG_TESTS=1`` and use a migrated Postgres ``DATABASE_URL`` with seed data
for analyses/shipments/items/provenance before enabling substantive tests here.

For CI without DB fixtures, this module is skipped.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PHASE2_PG_TESTS", "") != "1",
    reason="Set RUN_PHASE2_PG_TESTS=1 with migrated Postgres + seed data to run integration tests",
)


def test_phase2_integration_placeholder():
    """Reserved: same-analysis retry idempotency + DB-only replay with real FK rows."""
    pytest.skip("Add seeded fixtures (org, shipment, items, line provenance) then assert snapshot counts")
