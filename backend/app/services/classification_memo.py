"""
Classification memo + stable outcome (Sprint D, PATCH A).

Isolated module so tests and exports do not import shipment orchestration (S3, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config import settings


def _primary_candidate_dict(classification: Dict[str, Any]) -> Dict[str, Any]:
    pc = classification.get("primary_candidate")
    if isinstance(pc, dict):
        return pc
    cands = classification.get("candidates") or []
    return cands[0] if cands and isinstance(cands[0], dict) else {}


def _retrieval_similarity_diagnostic(classification: Dict[str, Any]) -> Optional[float]:
    pc = _primary_candidate_dict(classification)
    if not isinstance(pc, dict):
        return None
    try:
        if pc.get("similarity_score") is None:
            return None
        return float(pc["similarity_score"])
    except (TypeError, ValueError):
        return None


def _memo_best_similarity(classification: Dict[str, Any]) -> Optional[float]:
    """Extract the best similarity score from classification metadata or candidates."""
    meta = classification.get("metadata") or {}
    bs = meta.get("best_similarity")
    if bs is not None:
        try:
            return float(bs)
        except (TypeError, ValueError):
            pass
    cands = classification.get("candidates") or []
    sims = []
    for c in cands:
        s = c.get("similarity_score") if isinstance(c, dict) else None
        if s is not None:
            try:
                sims.append(float(s))
            except (TypeError, ValueError):
                pass
    return max(sims) if sims else None


def _build_classification_memo_strict(classification: Dict[str, Any]) -> Dict[str, Any]:
    """
    PATCH A: Engine `status` drives trust; lexical similarity is only diagnostic (optional field).
    """
    questions = classification.get("questions") or []
    if classification.get("status") == "CLARIFICATION_REQUIRED" or questions:
        return {
            "support_level": "needs_input",
            "support_label": "Needs input",
            "summary": classification.get("blocking_reason")
            or classification.get("error_reason")
            or "Additional product facts are required before a reliable classification can be stated.",
            "suppress_alternatives": True,
            "open_questions": questions,
            "trust_basis": "engine_status",
        }

    st = classification.get("status")
    sim_diag = _retrieval_similarity_diagnostic(classification)
    pc = _primary_candidate_dict(classification)
    hts = pc.get("hts_code") if isinstance(pc, dict) else None

    if st == "SUCCESS":
        return {
            "support_level": "supported",
            "support_label": "Supported",
            "proposed_hts": hts,
            "suppress_alternatives": False,
            "summary": (
                "Engine status SUCCESS (combined score / facts met gates per status model). "
                "Confirm against your evidence and broker—lexical match to tariff text is not the sole criterion."
            ),
            "open_questions": questions,
            "retrieval_lexical_similarity_diagnostic": sim_diag,
            "trust_basis": "engine_status",
        }

    if st == "REVIEW_REQUIRED":
        rev = classification.get("review_explanation") or {}
        pr = rev.get("primary_reasons") or []
        summary = "; ".join(str(x) for x in pr[:5]) if pr else "Classification requires human review."
        return {
            "support_level": "insufficient_support",
            "support_label": "Review required",
            "proposed_hts": hts,
            "suppress_alternatives": False,
            "summary": summary,
            "open_questions": questions,
            "retrieval_lexical_similarity_diagnostic": sim_diag,
            "trust_basis": "engine_status",
        }

    err = classification.get("error")
    if err or st in ("NO_CONFIDENT_MATCH", "NO_GOOD_MATCH") or classification.get("success") is False:
        best_sim = _memo_best_similarity(classification)
        if best_sim is not None and best_sim < 0.15:
            return {
                "support_level": "no_classification",
                "support_label": "No classification possible",
                "summary": (
                    classification.get("error_reason")
                    or "Retrieval similarity to tariff text is extremely low and no confident match was produced."
                ),
                "suppress_alternatives": True,
                "open_questions": [],
                "retrieval_lexical_similarity_diagnostic": best_sim,
                "trust_basis": "retrieval_and_gates",
            }
        return {
            "support_level": "insufficient_support",
            "support_label": "Insufficient support",
            "summary": classification.get("error_reason")
            or err
            or "No reliable classification generated from current evidence.",
            "suppress_alternatives": False,
            "open_questions": [],
            "trust_basis": "retrieval_and_gates",
        }

    return {
        "support_level": "insufficient_support",
        "support_label": "Insufficient support",
        "proposed_hts": hts,
        "suppress_alternatives": False,
        "summary": "Classification output could not be mapped to a standard engine status; treat as unverified.",
        "open_questions": questions,
        "retrieval_lexical_similarity_diagnostic": sim_diag,
        "trust_basis": "unknown",
    }


def _build_classification_memo_legacy(classification: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy memo: lexical similarity bands can influence support_level (pre–PATCH A)."""
    questions = classification.get("questions") or []
    if classification.get("status") == "CLARIFICATION_REQUIRED" or questions:
        return {
            "support_level": "needs_input",
            "support_label": "Needs input",
            "summary": classification.get("blocking_reason")
            or classification.get("error_reason")
            or "Additional product facts are required before a reliable classification can be stated.",
            "suppress_alternatives": True,
            "open_questions": questions,
        }
    err = classification.get("error")
    st = classification.get("status")
    if err or st in ("NO_CONFIDENT_MATCH", "NO_GOOD_MATCH") or classification.get("success") is False:
        best_sim = _memo_best_similarity(classification)
        if best_sim is not None and best_sim < 0.15:
            return {
                "support_level": "no_classification",
                "support_label": "No classification possible",
                "summary": (
                    classification.get("error_reason")
                    or "Similarity to any tariff heading is extremely low. "
                    "Cannot generate a reliable classification from current evidence."
                ),
                "suppress_alternatives": True,
                "open_questions": [],
            }
        return {
            "support_level": "insufficient_support",
            "support_label": "Insufficient support",
            "summary": classification.get("error_reason")
            or err
            or "No reliable classification generated from current evidence.",
            "suppress_alternatives": False,
            "open_questions": [],
        }
    pc = classification.get("primary_candidate")
    if not pc:
        cands = classification.get("candidates") or []
        pc = cands[0] if cands else None
    hts = pc.get("hts_code") if isinstance(pc, dict) else None
    if isinstance(pc, dict):
        sim = pc.get("similarity_score")
        try:
            sim_f = float(sim) if sim is not None else None
        except (TypeError, ValueError):
            sim_f = None
        if sim_f is not None and sim_f < 0.15 and hts:
            return {
                "support_level": "no_classification",
                "support_label": "No classification possible",
                "proposed_hts": None,
                "similarity_score": sim_f,
                "summary": "Similarity to tariff language is extremely low; no reliable classification can be stated.",
                "suppress_alternatives": True,
                "open_questions": questions,
            }
        if sim_f is not None and sim_f < 0.22 and hts:
            return {
                "support_level": "weak_support",
                "support_label": "Weak match — verify",
                "proposed_hts": hts,
                "similarity_score": sim_f,
                "suppress_alternatives": False,
                "summary": (
                    "Textual similarity to tariff language is low; this is a hypothesis to verify against "
                    "your product evidence and broker—not a determination."
                ),
                "open_questions": questions,
            }
    return {
        "support_level": "supported",
        "support_label": "Supported",
        "proposed_hts": hts,
        "suppress_alternatives": False,
        "summary": "A classification suggestion is available; confirm against your evidence and broker.",
        "open_questions": questions,
    }


_OUTCOME_VOCABULARY = {
    "no_classification": "NO_CLASSIFICATION_POSSIBLE",
    "needs_input": "NEEDS_INPUT",
    "insufficient_support": "INSUFFICIENT_SUPPORT",
    "weak_support": "INSUFFICIENT_SUPPORT",
    "supported": "SUPPORTED",
}


def stable_classification_outcome(support_level: str) -> str:
    """Map internal support_level to the stable API classification_outcome enum."""
    return _OUTCOME_VOCABULARY.get(support_level, "UNKNOWN")


def build_classification_memo(classification: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sprint D — human-readable classification trust layer (no fake precision).

    PATCH A: When ``settings.CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT`` is True, engine
    ``status`` drives trust; lexical similarity is exposed as ``retrieval_lexical_similarity_diagnostic`` only.
    """
    if not classification or not isinstance(classification, dict):
        return {
            "support_level": "no_classification",
            "support_label": "No classification possible",
            "summary": "No classification output was produced for this item.",
            "suppress_alternatives": True,
            "open_questions": [],
        }
    if getattr(settings, "CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT", False):
        return _build_classification_memo_strict(classification)
    return _build_classification_memo_legacy(classification)
