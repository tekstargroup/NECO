"""
Patch F — Grounded classification chat (cite-or-refuse).

Answers are assembled only from stored analysis JSON: facts, heading trace,
evidence_used / line provenance, and classification blocks. No web or LLM required.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID


def _norm(s: str) -> str:
    return (s or "").lower().strip()


def _detect_intent(message: str) -> str:
    m = _norm(message)
    if not m:
        return "empty"
    if any(
        p in m
        for p in (
            "why are you asking",
            "why do you ask",
            "why this question",
            "why are these questions",
        )
    ):
        return "clarification_why"
    if any(
        p in m
        for p in (
            "reject",
            "rejected",
            "did not choose",
            "didn't choose",
            "alternative heading",
            "other heading",
            "not pick",
        )
    ):
        return "rejected"
    if any(p in m for p in ("which document", "what document", "supports", "evidence for", "prove", "source for")):
        return "document_evidence"
    if any(p in m for p in ("missing", "what fact", "which fact", "don't know", "do not know", "not enough")):
        return "missing_facts"
    if any(
        p in m
        for p in (
            "why here",
            "why this classification",
            "why did you route",
            "why route",
            "why pick",
            "why chose",
            "how did you",
            "rationale",
        )
    ):
        return "routing"
    return "unknown"


def _find_item(
    items: List[Dict[str, Any]], shipment_item_id: Optional[UUID]
) -> Tuple[int, Dict[str, Any]]:
    if not items:
        return -1, {}
    if shipment_item_id is None:
        return 0, items[0]
    sid = str(shipment_item_id)
    for i, it in enumerate(items):
        if str(it.get("id")) == sid:
            return i, it
    return -1, {}


def _fmt_list(xs: Any, maxn: int = 12) -> str:
    if not isinstance(xs, list):
        return ""
    out = []
    for x in xs[:maxn]:
        if isinstance(x, dict):
            out.append(str(x.get("attribute") or x.get("hts_code") or x))
        else:
            out.append(str(x))
    return "; ".join(out)


def _answer_clarification_why(item: Dict[str, Any], path_prefix: str) -> Tuple[str, List[Dict[str, Any]]]:
    cites: List[Dict[str, Any]] = []
    clf = item.get("classification") if isinstance(item.get("classification"), dict) else {}
    meta = (clf or {}).get("metadata") or {}
    questions = (clf or {}).get("questions") or meta.get("clarification_questions") or []
    memo = item.get("classification_memo") if isinstance(item.get("classification_memo"), dict) else {}
    blocking = (clf or {}).get("blocking_reason") or meta.get("blocking_reason") or memo.get("summary")
    parts = []
    if blocking:
        parts.append(f"**Blocking reason (from stored classification):** {blocking}")
        cites.append({"path": f"{path_prefix}.classification", "label": "classification.blocking / memo"})
    if questions:
        parts.append("**Clarification prompts tied to missing or weak facts:**")
        for q in questions[:10]:
            if isinstance(q, dict):
                attr = q.get("attribute", "")
                qq = q.get("question", "")
                parts.append(f"- **{attr}:** {qq}")
            else:
                parts.append(f"- {q}")
        cites.append({"path": f"{path_prefix}.classification.questions", "label": "Engine clarification questions"})
    trace = item.get("heading_reasoning_trace") or {}
    amb = trace.get("unresolved_ambiguity") or {}
    if amb.get("missing_facts"):
        parts.append(f"**Facts still treated as missing:** {_fmt_list(amb['missing_facts'])}")
        cites.append({"path": f"{path_prefix}.heading_reasoning_trace.unresolved_ambiguity", "label": "Trace: missing facts"})
    if not parts:
        return "", []
    return "\n\n".join(parts), cites


def _answer_rejected(
    item: Dict[str, Any], path_prefix: str
) -> Union[Tuple[str, List[Dict[str, Any]]], Dict[str, Any]]:
    trace = item.get("heading_reasoning_trace") or {}
    rej = trace.get("rejected_alternatives") or []
    cites = [{"path": f"{path_prefix}.heading_reasoning_trace.rejected_alternatives", "label": "Rejected ranked alternatives"}]
    if not rej:
        return {
            "answer": (
                "There is **no stored list of deprioritized alternatives** for this line in the analysis snapshot "
                "(empty `rejected_alternatives`). I cannot invent rejected headings."
            ),
            "citations": [],
            "refusal": True,
            "intent": "rejected",
        }
    lines = ["**Lower-ranked alternatives (from analysis trace):**"]
    for r in rej[:8]:
        if not isinstance(r, dict):
            continue
        code = r.get("hts_code") or "—"
        reason = r.get("reason") or "—"
        fs = r.get("final_score")
        lines.append(f"- `{code}` — {reason}" + (f" (score {fs})" if fs is not None else ""))
    return "\n".join(lines), cites


def _answer_documents(item: Dict[str, Any], path_prefix: str, evidence_map: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    cites: List[Dict[str, Any]] = []
    ev = item.get("evidence_used") or []
    lp = item.get("line_provenance") or []
    se = (item.get("heading_reasoning_trace") or {}).get("source_evidence") or {}
    parts = []
    if ev:
        parts.append("**Evidence links for this line (`evidence_used`):**")
        for e in ev[:15]:
            if isinstance(e, dict):
                parts.append(
                    f"- Document `{e.get('document_id', '—')}` ({e.get('document_type', 'type ?')}): "
                    f"{str(e.get('snippet') or e.get('text_excerpt') or '')[:240]}"
                )
            else:
                parts.append(f"- {e}")
        cites.append({"path": f"{path_prefix}.evidence_used", "label": "Line evidence_used"})
    if lp:
        parts.append("**Line provenance (where the line was extracted):**")
        for p in lp[:10]:
            if isinstance(p, dict):
                parts.append(
                    f"- Doc `{p.get('document_id', '—')}`, page/line ref: {p.get('page') or p.get('source_location') or '—'}"
                )
            else:
                parts.append(f"- {p}")
        cites.append({"path": f"{path_prefix}.line_provenance", "label": "Line provenance"})
    tc = se.get("tariff_context") if isinstance(se, dict) else None
    if tc and (tc.get("code_ids") or tc.get("source_pages")):
        parts.append(f"**Tariff context pointers:** {tc}")
        cites.append({"path": f"{path_prefix}.heading_reasoning_trace.source_evidence", "label": "Tariff context"})

    if not parts and evidence_map.get("documents"):
        parts.append(
            "**Shipment-level documents** are listed in `evidence_map.documents` in this analysis, "
            "but this line has no `evidence_used` rows. I cannot tie a document to this line without that mapping."
        )
        cites.append(
            {
                "path": "result_json.evidence_map.documents",
                "label": "Shipment documents (not line-specific)",
                "scope": "shipment_not_line",
            }
        )
    if not parts:
        return "", []
    return "\n\n".join(parts), cites


def _answer_missing(item: Dict[str, Any], path_prefix: str) -> Tuple[str, List[Dict[str, Any]]]:
    cites: List[Dict[str, Any]] = []
    facts = item.get("classification_facts") or {}
    missing = facts.get("missing_facts") or []
    trace = item.get("heading_reasoning_trace") or {}
    amb = trace.get("unresolved_ambiguity") or {}
    mf = amb.get("missing_facts") or []
    meta_m = []
    clf = item.get("classification") if isinstance(item.get("classification"), dict) else {}
    md = (clf.get("metadata") or {}) if clf else {}
    if isinstance(md.get("missing_required_attributes"), list):
        meta_m = md["missing_required_attributes"]

    merged = list(dict.fromkeys([str(x) for x in (missing or [])] + [str(x) for x in (mf or [])] + [str(x) for x in meta_m]))
    parts = []
    if merged:
        parts.append("**Facts flagged as missing or incomplete:**")
        for x in merged[:20]:
            parts.append(f"- {x}")
        cites.append({"path": f"{path_prefix}.classification_facts.missing_facts", "label": "classification_facts"})
        cites.append({"path": f"{path_prefix}.heading_reasoning_trace.unresolved_ambiguity", "label": "Trace ambiguity"})
    wwi = amb.get("what_would_increase_confidence") or []
    if wwi:
        parts.append("**What would increase confidence (from trace):**")
        for w in wwi[:8]:
            parts.append(f"- {w}")
    if not parts:
        return "", []
    return "\n\n".join(parts), cites


def _answer_routing(item: Dict[str, Any], path_prefix: str) -> Tuple[str, List[Dict[str, Any]]]:
    cites: List[Dict[str, Any]] = []
    trace = item.get("heading_reasoning_trace") or {}
    ch = trace.get("chapter_and_heading_rationale") or []
    ret = trace.get("retrieval_and_narrowing") or {}
    hc = trace.get("heading_candidates") or []

    parts = []
    if ch:
        parts.append("**Chapter / heading rationale (product analysis + clusters):**")
        for row in ch[:5]:
            if not isinstance(row, dict):
                continue
            parts.append(
                f"- Chapter **{row.get('chapter')}** — {row.get('product_analysis_reason') or ''} "
                f"{('Cluster: ' + row['cluster_rationale']) if row.get('cluster_rationale') else ''}"
            )
        cites.append({"path": f"{path_prefix}.heading_reasoning_trace.chapter_and_heading_rationale", "label": "Chapter rationale"})

    if ret:
        parts.append("**Retrieval & narrowing:**")
        if ret.get("headings_used"):
            parts.append(f"- Headings used in retrieval: `{ret['headings_used']}`")
        if ret.get("gating_mode"):
            parts.append(f"- Gating mode: `{ret['gating_mode']}`")
        if ret.get("rule_reasoning_path"):
            parts.append(f"- Rule reasoning path: {ret['rule_reasoning_path']}")
        if ret.get("alternative_headings_considered"):
            parts.append(f"- Alternative headings considered (rules): {ret['alternative_headings_considered']}")
        cites.append({"path": f"{path_prefix}.heading_reasoning_trace.retrieval_and_narrowing", "label": "Retrieval trace"})

    if hc:
        top = hc[0] if isinstance(hc[0], dict) else {}
        parts.append(
            f"**Primary ranked line:** `{top.get('hts_code')}` (heading {top.get('heading')}, score {top.get('final_score')})."
        )
        cites.append({"path": f"{path_prefix}.heading_reasoning_trace.heading_candidates", "label": "Ranked heading candidates"})

    memo = item.get("classification_memo") or {}
    if memo.get("summary"):
        parts.append(f"**Classification memo:** {memo.get('summary')}")
        cites.append({"path": f"{path_prefix}.classification_memo", "label": "classification_memo"})

    if not parts:
        return "", []
    return "\n\n".join(parts), cites


def build_grounded_answer(
    result_json: Dict[str, Any],
    message: str,
    shipment_item_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Return { answer, citations, refusal, intent, item_index, item_id }.
    """
    intent = _detect_intent(message)
    items = result_json.get("items") or []
    if not isinstance(items, list):
        items = []

    idx, item = _find_item(items, shipment_item_id)
    if idx < 0 or not item:
        return {
            "answer": "This analysis has **no line items** in `result_json.items`, so there is nothing to ground an answer on.",
            "citations": [],
            "refusal": True,
            "intent": intent,
            "item_index": None,
            "item_id": None,
        }

    path_prefix = f"result_json.items[{idx}]"
    evidence_map = result_json.get("evidence_map") if isinstance(result_json.get("evidence_map"), dict) else {}

    if intent == "empty":
        return {
            "answer": "Ask a specific question about this line (routing, missing facts, documents, rejected headings, or why we asked for clarification).",
            "citations": [],
            "refusal": True,
            "intent": "empty",
            "item_index": idx,
            "item_id": str(item.get("id")),
        }

    handlers = {
        "clarification_why": _answer_clarification_why,
        "rejected": _answer_rejected,
        "document_evidence": lambda it, p: _answer_documents(it, p, evidence_map),
        "missing_facts": _answer_missing,
        "routing": _answer_routing,
    }

    if intent in handlers:
        raw = handlers[intent](item, path_prefix)
        if isinstance(raw, dict):
            scope = ""
            if shipment_item_id is None and len(items) > 1:
                scope = (
                    f"\n\n*(Answering for **line {idx + 1}** / item `{item.get('id')}` — "
                    f"pass `shipment_item_id` to target another line.)*"
                )
            out = {
                **raw,
                "item_index": idx,
                "item_id": str(item.get("id")),
            }
            if scope and raw.get("answer"):
                out["answer"] = str(raw["answer"]) + scope
            return out
        text, cites = raw
        if text:
            scope = ""
            if shipment_item_id is None and len(items) > 1:
                scope = (
                    f"\n\n*(Answering for **line {idx + 1}** / item `{item.get('id')}` — "
                    f"pass `shipment_item_id` to target another line.)*"
                )
            return {
                "answer": text + scope,
                "citations": cites,
                "refusal": False,
                "intent": intent,
                "item_index": idx,
                "item_id": str(item.get("id")),
            }

    # unknown or handler returned empty — refuse honestly
    return {
        "answer": (
            "I can only use **facts, trace, evidence, and classification fields** stored in this analysis run. "
            "Either your question doesn't match a supported pattern, or the evidence fields needed to answer it are empty. "
            "Try: “Why did you route this here?”, “What fact is missing?”, “What document supports that?”, "
            "“What alternative heading did you reject?”, or “Why are you asking me this question?”"
        ),
        "citations": [],
        "refusal": True,
        "intent": intent if intent != "unknown" else "unsupported",
        "item_index": idx,
        "item_id": str(item.get("id")),
    }
