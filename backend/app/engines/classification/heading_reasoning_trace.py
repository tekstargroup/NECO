"""
Patch E — Heading-first reasoning and explanation trace.

Builds a broker-style trace: what was considered, what was deprioritized, why,
subheading narrowing signals, unresolved ambiguity, and document/tariff evidence hooks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.engines.classification.chapter_clusters import get_cluster_rationale


def _norm_hts_digits(code: Optional[str]) -> str:
    if not code:
        return ""
    return "".join(c for c in str(code) if c.isdigit())


def _heading_from_hts(hts_code: Optional[str]) -> str:
    d = _norm_hts_digits(hts_code)
    return d[:4] if len(d) >= 4 else ""


def _chapter_from_heading(heading: str) -> Optional[int]:
    if len(heading) >= 2:
        try:
            return int(heading[:2])
        except ValueError:
            return None
    return None


def _safe_pa(meta: Dict[str, Any]) -> Dict[str, Any]:
    pa = meta.get("product_analysis")
    if isinstance(pa, dict):
        return pa
    return {}


def _merge_clarification_overlay(classification_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    When the pipeline short-circuits to CLARIFICATION_REQUIRED, prefer the underlying
    engine response for heading/trace context while preserving the blocking overlay.
    """
    if classification_result.get("status") != "CLARIFICATION_REQUIRED":
        return classification_result
    orig = classification_result.get("original_classification")
    if not isinstance(orig, dict):
        return classification_result
    merged = dict(orig)
    merged["clarification_required_overlay"] = {
        "blocking_reason": classification_result.get("blocking_reason"),
        "questions": classification_result.get("questions"),
    }
    merged["pipeline_blocked_as"] = "CLARIFICATION_REQUIRED"
    return merged


def build_heading_reasoning_trace(
    classification_result: Optional[Dict[str, Any]],
    *,
    evidence_used: Optional[List[Dict[str, Any]]] = None,
    line_provenance: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Assemble a versioned trace from a classification engine response (+ shipment evidence).

    Works for SUCCESS, REVIEW_REQUIRED, NO_CONFIDENT_MATCH, CLARIFICATION_REQUIRED, and error stubs.

    Pass ``classification_result=None`` when the API withholds classification alternatives
    (``suppress_alternatives``) so the trace does not expose ranked headings while ``classification`` is null.
    Document/line evidence may still be attached from ``evidence_used`` / ``line_provenance``.
    """
    out: Dict[str, Any] = {
        "schema_version": "1",
        "heading_candidates": [],
        "chapter_and_heading_rationale": [],
        "retrieval_and_narrowing": {},
        "rejected_alternatives": [],
        "subheading_narrowing": [],
        "unresolved_ambiguity": {},
        "source_evidence": {},
    }

    if not classification_result or not isinstance(classification_result, dict):
        out["unresolved_ambiguity"] = {
            "notes": ["No classification result available for this line."],
        }
        _attach_evidence(out, evidence_used, line_provenance, None)
        return out

    classification_result = _merge_clarification_overlay(classification_result)

    if classification_result.get("error") and not classification_result.get("candidates"):
        out["unresolved_ambiguity"] = {
            "engine_error": str(classification_result.get("error")),
            "notes": ["Classification engine did not return ranked candidates."],
        }
        _attach_evidence(out, evidence_used, line_provenance, classification_result.get("provenance"))
        return out

    meta = classification_result.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}

    pa = _safe_pa(meta)
    product_family = pa.get("product_family") or meta.get("detected_product_family")
    suggested = pa.get("suggested_chapters") or meta.get("suggested_chapters") or []

    # Chapter / heading rationale (product analysis + cluster text)
    rationale_rows: List[Dict[str, Any]] = []
    if isinstance(suggested, list):
        for ch_entry in suggested[:5]:
            if not isinstance(ch_entry, dict):
                continue
            ch = ch_entry.get("chapter")
            reason = ch_entry.get("reason") or ""
            conf = ch_entry.get("confidence")
            cluster_text = ""
            if product_family and ch is not None:
                try:
                    cluster_text = get_cluster_rationale(str(product_family), int(ch))
                except (TypeError, ValueError):
                    cluster_text = ""
            rationale_rows.append(
                {
                    "chapter": ch,
                    "confidence": conf,
                    "product_analysis_reason": reason,
                    "cluster_rationale": cluster_text or None,
                }
            )
    out["chapter_and_heading_rationale"] = rationale_rows

    # Retrieval funnel
    narrowing: Dict[str, Any] = {
        "gating_mode": meta.get("gating_mode"),
        "headings_used": meta.get("headings_used") or [],
        "candidate_counts": meta.get("candidate_counts") or {},
        "expanded_query_terms": meta.get("expanded_terms") or [],
        "applied_filters": meta.get("applied_filters") or [],
        "applied_priors": meta.get("applied_priors") or [],
        "reason_code": meta.get("reason_code"),
        "rule_based_heading": meta.get("rule_based_heading"),
        "rule_based_confidence": meta.get("rule_based_confidence"),
    }
    rule_asm = classification_result.get("rule_based_assessment")
    if isinstance(rule_asm, dict):
        narrowing["rule_justification"] = rule_asm.get("justification")
        narrowing["alternative_headings_considered"] = rule_asm.get("alternative_headings_considered") or []
        narrowing["rule_reasoning_path"] = rule_asm.get("reasoning_path") or []
        narrowing["rule_warnings"] = rule_asm.get("warnings") or []
    out["retrieval_and_narrowing"] = narrowing

    candidates = classification_result.get("candidates") or []
    if not isinstance(candidates, list):
        candidates = []

    # Heading-level candidate summary (top ranked lines)
    heading_candidates: List[Dict[str, Any]] = []
    for i, c in enumerate(candidates[:8]):
        if not isinstance(c, dict):
            continue
        hts = c.get("hts_code") or ""
        hd = _heading_from_hts(hts)
        ch = c.get("hts_chapter") or (str(_chapter_from_heading(hd)) if hd else None)
        role = "selected_primary" if i == 0 else f"ranked_alternative_{i + 1}"
        heading_candidates.append(
            {
                "rank": i + 1,
                "heading": hd,
                "chapter": ch,
                "hts_code": hts,
                "final_score": c.get("final_score"),
                "similarity_score": c.get("similarity_score"),
                "role": role,
                "rule_injected": bool(c.get("rule_injected")),
                "tariff_text_short": (c.get("tariff_text_short") or "")[:200] or None,
            }
        )
    out["heading_candidates"] = heading_candidates

    # Deprioritized / not selected (broker narrative)
    rejected: List[Dict[str, Any]] = []
    if len(candidates) > 1:
        primary = candidates[0] if isinstance(candidates[0], dict) else {}
        primary_score = primary.get("final_score")
        primary_h = _heading_from_hts(primary.get("hts_code"))
        for j, c in enumerate(candidates[1:6], start=2):
            if not isinstance(c, dict):
                continue
            alt_h = _heading_from_hts(c.get("hts_code"))
            why = "lower_composite_score_than_primary"
            if primary_h and alt_h and primary_h != alt_h:
                why = "different_heading_than_primary_lower_rank"
            rejected.append(
                {
                    "rank": j,
                    "hts_code": c.get("hts_code"),
                    "heading": alt_h,
                    "final_score": c.get("final_score"),
                    "similarity_score": c.get("similarity_score"),
                    "reason": why,
                    "gap_vs_primary_score": _gap(primary_score, c.get("final_score")),
                }
            )
    out["rejected_alternatives"] = rejected

    # Subheading narrowing (priors attached to ranked lines)
    pri_lines: List[Dict[str, Any]] = []
    for i, c in enumerate(candidates[:5]):
        if not isinstance(c, dict):
            continue
        pri = c.get("_applied_priors")
        if pri:
            pri_lines.append(
                {
                    "rank": i + 1,
                    "hts_code": c.get("hts_code"),
                    "applied_priors": pri,
                }
            )
    if meta.get("applied_priors"):
        pri_lines.append(
            {
                "rank": 0,
                "hts_code": None,
                "applied_priors": meta.get("applied_priors"),
                "note": "aggregated across top candidates",
            }
        )
    out["subheading_narrowing"] = pri_lines

    # Ambiguity + missing facts
    status = classification_result.get("status")
    pipeline_blocked = classification_result.get("pipeline_blocked_as")
    review_ex = classification_result.get("review_explanation")
    amb: Dict[str, Any] = {"classification_status": pipeline_blocked or status}
    notes: List[str] = []
    if isinstance(review_ex, dict):
        pr = review_ex.get("primary_reasons") or []
        wwi = review_ex.get("what_would_increase_confidence") or []
        if pr:
            amb["primary_reasons"] = pr
        if wwi:
            amb["what_would_increase_confidence"] = wwi
        notes.extend([str(x) for x in pr if x])
    ar = meta.get("ambiguity_reason")
    if isinstance(ar, str) and ar.strip():
        amb["ambiguity_reason"] = ar
        notes.append(ar)
    elif isinstance(ar, list):
        amb["ambiguity_reason"] = ar
        notes.extend([str(x) for x in ar])

    missing_attrs = meta.get("missing_required_attributes") or pa.get("missing_required_attributes")
    if isinstance(missing_attrs, list) and missing_attrs:
        amb["missing_facts"] = missing_attrs

    overlay = classification_result.get("clarification_required_overlay")
    if isinstance(overlay, dict):
        amb["clarification_block"] = True
        if overlay.get("blocking_reason"):
            amb["blocking_reason"] = overlay.get("blocking_reason")
        oqs = overlay.get("questions") or []
        if oqs:
            amb["clarification_questions"] = oqs

    if (
        pipeline_blocked == "CLARIFICATION_REQUIRED"
        or classification_result.get("status") == "CLARIFICATION_REQUIRED"
        or meta.get("reason_code") == "MISSING_REQUIRED_ATTRIBUTES"
    ):
        amb["blocking"] = True
        qs = classification_result.get("questions") or []
        if qs and not amb.get("clarification_questions"):
            amb["clarification_questions"] = qs

    if not notes and not amb.get("primary_reasons"):
        if status in ("REVIEW_REQUIRED", "NO_CONFIDENT_MATCH", "CLARIFICATION_REQUIRED"):
            amb["notes"] = [f"Status {status} — see primary_reasons or engine metadata when present."]
        else:
            amb["notes"] = []
    else:
        amb["notes"] = notes

    out["unresolved_ambiguity"] = amb

    _attach_evidence(out, evidence_used, line_provenance, classification_result.get("provenance"))
    return out


def _gap(primary: Any, alt: Any) -> Optional[float]:
    try:
        if primary is None or alt is None:
            return None
        return float(primary) - float(alt)
    except (TypeError, ValueError):
        return None


def _attach_evidence(
    out: Dict[str, Any],
    evidence_used: Optional[List[Dict[str, Any]]],
    line_provenance: Optional[List[Dict[str, Any]]],
    provenance: Any,
) -> None:
    src: Dict[str, Any] = {}
    if evidence_used:
        src["document_evidence_refs"] = evidence_used
    if line_provenance:
        src["line_provenance"] = line_provenance
    if isinstance(provenance, dict):
        src["tariff_context"] = {
            "source_pages": provenance.get("source_pages"),
            "code_ids": provenance.get("code_ids"),
        }
    out["source_evidence"] = src
