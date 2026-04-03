"""Patch F — grounded classification chat."""

import uuid

from app.services.grounded_classification_chat_service import build_grounded_answer


def _sample_result():
    iid = str(uuid.uuid4())
    return {
        "shipment_id": str(uuid.uuid4()),
        "items": [
            {
                "id": iid,
                "label": "Test widget",
                "classification_memo": {"summary": "memo"},
                "heading_reasoning_trace": {
                    "chapter_and_heading_rationale": [
                        {
                            "chapter": 85,
                            "product_analysis_reason": "Electrical",
                            "cluster_rationale": "Ch85 electrical",
                        }
                    ],
                    "retrieval_and_narrowing": {
                        "headings_used": ["8518"],
                        "gating_mode": "two_stage",
                        "rule_reasoning_path": ["start", "pick 8518"],
                        "alternative_headings_considered": ["8479"],
                    },
                    "heading_candidates": [
                        {"hts_code": "8518.30.20", "heading": "8518", "final_score": 0.8},
                    ],
                    "rejected_alternatives": [
                        {"hts_code": "8518.50.00", "reason": "lower_composite_score_than_primary", "final_score": 0.5},
                    ],
                    "unresolved_ambiguity": {"missing_facts": ["material"]},
                    "source_evidence": {"tariff_context": {"code_ids": ["8518.30.20"]}},
                },
                "classification_facts": {"missing_facts": ["material"]},
                "evidence_used": [{"document_id": "d1", "document_type": "COMMERCIAL_INVOICE", "snippet": "widget"}],
                "line_provenance": [{"document_id": "d1", "page": 2}],
                "classification": {
                    "questions": [{"attribute": "material", "question": "What is it made of?"}],
                    "blocking_reason": "Need material",
                },
            }
        ],
        "evidence_map": {"documents": [{"id": "d1"}]},
    }


def test_routing_intent():
    rj = _sample_result()
    out = build_grounded_answer(rj, "Why did you route this here?")
    assert out["refusal"] is False
    assert out["intent"] == "routing"
    assert "8518" in out["answer"]
    assert any("heading_reasoning_trace" in c["path"] for c in out["citations"])


def test_rejected_intent():
    rj = _sample_result()
    out = build_grounded_answer(rj, "What alternative heading did you reject?")
    assert "8518.50" in out["answer"]
    assert out["refusal"] is False


def test_rejected_empty_list_is_refusal():
    rj = _sample_result()
    rj["items"][0]["heading_reasoning_trace"]["rejected_alternatives"] = []
    out = build_grounded_answer(rj, "What heading did you reject?")
    assert out["intent"] == "rejected"
    assert out["refusal"] is True
    assert "cannot invent" in out["answer"].lower()


def test_refuse_unknown():
    rj = _sample_result()
    out = build_grounded_answer(rj, "What is the weather in Paris?")
    assert out["refusal"] is True


def test_multi_item_scope_note():
    iid2 = str(uuid.uuid4())
    rj = _sample_result()
    rj["items"].append(
        {
            "id": iid2,
            "label": "Other",
            "heading_reasoning_trace": {},
        }
    )
    out = build_grounded_answer(rj, "Why route here?", shipment_item_id=None)
    assert "line 1" in out["answer"].lower() or "line" in out["answer"].lower()
