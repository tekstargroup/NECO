"""PATCH A — strict memo alignment with engine status."""

import pytest

from app.core.config import settings
from app.services.classification_memo import build_classification_memo


def test_strict_success_ignores_low_lexical_similarity(monkeypatch):
    monkeypatch.setattr(settings, "CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT", True)
    clf = {
        "status": "SUCCESS",
        "success": True,
        "candidates": [
            {
                "hts_code": "8518.30.20",
                "similarity_score": 0.05,
                "final_score": 0.85,
            }
        ],
    }
    memo = build_classification_memo(clf)
    assert memo["support_level"] == "supported"
    assert memo.get("retrieval_lexical_similarity_diagnostic") == 0.05


def test_legacy_low_similarity_weak_support(monkeypatch):
    monkeypatch.setattr(settings, "CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT", False)
    clf = {
        "status": "SUCCESS",
        "success": True,
        "candidates": [
            {
                "hts_code": "8518.30.20",
                "similarity_score": 0.18,
                "final_score": 0.85,
            }
        ],
    }
    memo = build_classification_memo(clf)
    assert memo["support_level"] == "weak_support"


def test_strict_review_uses_engine_not_lexical(monkeypatch):
    monkeypatch.setattr(settings, "CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT", True)
    clf = {
        "status": "REVIEW_REQUIRED",
        "success": True,
        "candidates": [{"hts_code": "8518.30.20", "similarity_score": 0.9, "final_score": 0.3}],
        "review_explanation": {"primary_reasons": ["Multiple plausible subheadings"], "what_would_increase_confidence": ["x"]},
    }
    memo = build_classification_memo(clf)
    assert memo["support_level"] == "insufficient_support"
    assert "Multiple plausible" in memo["summary"]
