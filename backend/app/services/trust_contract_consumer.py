"""
Helpers for programmatic consumers of analysis `result_json` and exports.

Phase 1 rule: nothing should treat `decision_status=TRUSTED` as “everything in the payload is
authoritative.” Use `trust_contract` (especially `artifact_matrix` and `in_trusted_contract`)
or explicitly treat non-listed artifacts as advisory.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

Outcome = Literal["trusted_scope", "advisory", "unknown"]

EXPORT_ADVISORY_NOTICE = (
    "This export may include advisory-only fields (duty, PSC, prior knowledge). For Phase 2, canonical "
    "explanation artifacts are DB rows keyed by analysis_id (see trust_contract.artifact_matrix): "
    "classification facts, reasoning traces, regulatory evaluations, line_provenance_snapshot. "
    "Check in_trusted_contract per artifact before compliance use."
)

REASONING_AND_PROVENANCE_SUPPORTING_ONLY = (
    "Heading reasoning trace TRUSTED only when trust_contract enables it; frozen line provenance for the "
    "analysis run is analysis_line_provenance_snapshots (line_provenance_live_import is live shipment state)."
)


def get_trust_contract(result_json: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return embedded trust_contract dict or None."""
    if not result_json or not isinstance(result_json, dict):
        return None
    tc = result_json.get("trust_contract")
    return tc if isinstance(tc, dict) else None


def artifact_in_trusted_contract(artifact_key: str, trust_contract: Optional[Dict[str, Any]]) -> bool:
    """
    True if artifact_key appears in trust_contract.artifact_matrix with in_trusted_contract True.

    artifact_key should match the "artifact" field in the matrix (e.g. "classification_facts_db").
    """
    if not trust_contract:
        return False
    for row in trust_contract.get("artifact_matrix") or []:
        if not isinstance(row, dict):
            continue
        if row.get("artifact") == artifact_key and row.get("in_trusted_contract") is True:
            return True
    return False


def classify_artifact_scope(artifact_key: str, trust_contract: Optional[Dict[str, Any]]) -> Outcome:
    """Whether this artifact type is in the trusted contract, advisory, or unknown."""
    if not trust_contract:
        return "unknown"
    for row in trust_contract.get("artifact_matrix") or []:
        if not isinstance(row, dict):
            continue
        if row.get("artifact") == artifact_key:
            if row.get("in_trusted_contract") is True:
                return "trusted_scope"
            return "advisory"
    return "unknown"


def export_supplement_from_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Merge into export JSON so every pack carries contract + notices."""
    tc = snapshot.get("trust_contract") if isinstance(snapshot, dict) else None
    return {
        "trust_contract": tc if isinstance(tc, dict) else None,
        "export_advisory_notice": EXPORT_ADVISORY_NOTICE,
        "reasoning_and_provenance_notice": REASONING_AND_PROVENANCE_SUPPORTING_ONLY,
    }


def advisory_artifact_keys() -> List[str]:
    """Artifact keys that are often advisory (verify matrix; some are conditionally TRUSTED in Phase 2)."""
    return [
        "duty_resolution_json",
        "psc_json",
        "heading_reasoning_trace",
        "line_provenance_live_import",
    ]
