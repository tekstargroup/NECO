#!/usr/bin/env python3
"""
NECO Benchmark CLI — run the classification gold set through the trust pipeline
and print accuracy, false confidence, and per-case results.

Usage:
    python run_benchmark.py                # full table
    python run_benchmark.py --failures     # only show failures
    python run_benchmark.py --json         # machine-readable output
    python run_benchmark.py --category medical_devices  # filter by category
"""
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.engines.classification.rule_based_classifier import (
    RuleBasedClassifier,
    ProductInput,
)
from app.services.shipment_analysis_service import (
    build_classification_memo,
    stable_classification_outcome,
)
from app.services.analysis_pipeline import build_analysis_provenance

GOLD_SET_PATH = Path(__file__).parent / "tests" / "benchmark" / "classification_gold_set.json"


@dataclass
class CaseResult:
    case_id: str
    category: str
    difficulty: str
    description: str
    expected_heading: Optional[str]
    expected_outcome: str
    actual_heading: Optional[str]
    actual_outcome: str
    support_level: str
    confidence: str
    heading_match: bool
    outcome_match: bool
    false_confidence: bool
    reasoning_path: List[str]


def _build_product_input(case: Dict[str, Any]) -> ProductInput:
    """Mirror the _build_rule_product_input logic from shipment_analysis_service."""
    desc = (case.get("description") or "").lower()
    training_cues = ["simulator", "simulation", "training", "demonstration", "demonstrational"]
    medical_cues = ["surgical", "endoscopic", "endoscopy", "medical", "procedure", "patient", "clinical"]
    robotic_cues = ["robot", "robotic", "robot-assisted"]
    action_cues = ["grasp", "traction", "closure", "clip", "cut", "manipulat", "inserted"]
    system_cues = ["system", "controller", "driver unit", "cartridge", "platform"]

    is_training = any(c in desc for c in training_cues)
    is_medical = any(c in desc for c in medical_cues)
    is_robotic = any(c in desc for c in robotic_cues)
    performs_action = any(c in desc for c in action_cues)
    integrated_system = any(c in desc for c in system_cues)

    used_on_humans = False if is_training else (True if (is_medical and "training" not in desc) else None)
    purpose = "training" if is_training else ("treatment" if is_medical else "other")

    return ProductInput(
        product_name=case.get("description", ""),
        description=case.get("description", ""),
        used_on_humans=used_on_humans,
        purpose=purpose,
        is_robotic=is_robotic if is_robotic else None,
        is_medical_field=is_medical if is_medical else None,
        performs_direct_action=performs_action if performs_action else None,
        interacts_with_body=performs_action if performs_action else None,
        multiple_components=integrated_system if integrated_system else None,
        performs_integrated_function=integrated_system if integrated_system else None,
    )


def run_single_case(case: Dict[str, Any], classifier: RuleBasedClassifier) -> CaseResult:
    product = _build_product_input(case)
    result = classifier.classify(product)

    mock_classification: Optional[Dict[str, Any]] = None
    if result.heading:
        mock_classification = {
            "candidates": [{
                "hts_code": result.htsus or f"{result.heading}.00.00",
                "similarity_score": 0.85 if result.confidence == "high" else 0.5,
                "heading": result.heading,
            }],
            "metadata": {
                "top_candidate_hts": result.htsus or result.heading,
                "best_similarity": 0.85 if result.confidence == "high" else 0.5,
            },
        }

    description = case.get("description") or ""
    memo = build_classification_memo(mock_classification)
    support_level = memo.get("support_level", "unknown")
    actual_outcome = stable_classification_outcome(support_level)
    actual_heading = result.heading

    expected_heading = case.get("expected_hts_heading")
    expected_outcome_raw = case.get("expected_outcome", "")
    expected_outcome = stable_classification_outcome(expected_outcome_raw)

    heading_match = (
        actual_heading == expected_heading
        if expected_heading
        else actual_heading is None
    )
    outcome_match = actual_outcome == expected_outcome

    false_confidence = (
        not heading_match
        and result.confidence in ("high", "medium")
        and actual_heading is not None
    )

    return CaseResult(
        case_id=case["id"],
        category=case.get("category", ""),
        difficulty=case.get("difficulty", ""),
        description=description[:60],
        expected_heading=expected_heading,
        expected_outcome=expected_outcome,
        actual_heading=actual_heading,
        actual_outcome=actual_outcome,
        support_level=support_level,
        confidence=result.confidence,
        heading_match=heading_match,
        outcome_match=outcome_match,
        false_confidence=false_confidence,
        reasoning_path=result.reasoning_path,
    )


def main():
    parser = argparse.ArgumentParser(description="NECO Classification Benchmark CLI")
    parser.add_argument("--failures", action="store_true", help="Show only failures")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--gold-set", type=str, default=str(GOLD_SET_PATH), help="Path to gold set JSON")
    args = parser.parse_args()

    gold_set = json.loads(Path(args.gold_set).read_text())
    if args.category:
        gold_set = [c for c in gold_set if c.get("category") == args.category]

    classifier = RuleBasedClassifier()
    results: List[CaseResult] = []
    for case in gold_set:
        results.append(run_single_case(case, classifier))

    provenance = build_analysis_provenance(analysis_path="benchmark_cli", pipeline_mode="BENCHMARK")

    if args.json:
        _output_json(results, provenance)
    else:
        _output_table(results, provenance, failures_only=args.failures)


def _output_json(results: List[CaseResult], provenance: Dict[str, Any]):
    total = len(results)
    heading_correct = sum(1 for r in results if r.heading_match)
    outcome_correct = sum(1 for r in results if r.outcome_match)
    false_conf = sum(1 for r in results if r.false_confidence)

    output = {
        "provenance": provenance,
        "summary": {
            "total_cases": total,
            "heading_accuracy": heading_correct / total if total else 0,
            "outcome_accuracy": outcome_correct / total if total else 0,
            "false_confidence_count": false_conf,
            "false_confidence_rate": false_conf / total if total else 0,
        },
        "cases": [
            {
                "case_id": r.case_id,
                "category": r.category,
                "difficulty": r.difficulty,
                "expected_heading": r.expected_heading,
                "expected_outcome": r.expected_outcome,
                "actual_heading": r.actual_heading,
                "actual_outcome": r.actual_outcome,
                "heading_match": r.heading_match,
                "outcome_match": r.outcome_match,
                "false_confidence": r.false_confidence,
                "confidence": r.confidence,
                "support_level": r.support_level,
            }
            for r in results
        ],
    }
    print(json.dumps(output, indent=2))


def _output_table(results: List[CaseResult], provenance: Dict[str, Any], *, failures_only: bool = False):
    total = len(results)
    heading_correct = sum(1 for r in results if r.heading_match)
    outcome_correct = sum(1 for r in results if r.outcome_match)
    false_conf = sum(1 for r in results if r.false_confidence)

    print("=" * 100)
    print("NECO CLASSIFICATION BENCHMARK")
    print("=" * 100)
    print(f"  Schema:         {provenance.get('schema_version')}")
    print(f"  NECO version:   {provenance.get('neco_version')}")
    print(f"  HTS version:    {provenance.get('hts_version_id')}")
    print(f"  Rule mode:      {provenance.get('classification_rule_mode')}")
    print(f"  Rule hash:      {provenance.get('rule_registry_hash')}")
    print(f"  Generated:      {provenance.get('generated_at')}")
    print("-" * 100)

    show = [r for r in results if not failures_only or not (r.heading_match and r.outcome_match)]

    hdr = f"{'ID':<16} {'Cat':<18} {'Diff':<6} {'Exp.HD':<8} {'Act.HD':<8} {'HD':^4} {'Exp.Out':<26} {'Act.Out':<26} {'Out':^4} {'FC':^4}"
    print(hdr)
    print("-" * 100)

    for r in show:
        hd_mark = "OK" if r.heading_match else "XX"
        out_mark = "OK" if r.outcome_match else "XX"
        fc_mark = "!!" if r.false_confidence else "  "
        exp_hd = r.expected_heading or "None"
        act_hd = r.actual_heading or "None"
        print(
            f"{r.case_id:<16} {r.category:<18} {r.difficulty:<6} "
            f"{exp_hd:<8} {act_hd:<8} {hd_mark:^4} "
            f"{r.expected_outcome:<26} {r.actual_outcome:<26} {out_mark:^4} {fc_mark:^4}"
        )

    print("-" * 100)
    print(f"\nSUMMARY ({total} cases)")
    print(f"  Heading accuracy:       {heading_correct}/{total} ({heading_correct/total*100:.1f}%)" if total else "  No cases")
    print(f"  Outcome accuracy:       {outcome_correct}/{total} ({outcome_correct/total*100:.1f}%)" if total else "")
    print(f"  False confidence:       {false_conf}/{total} ({false_conf/total*100:.1f}%)" if total else "")

    by_cat: Dict[str, List[CaseResult]] = defaultdict(list)
    for r in results:
        by_cat[r.category].append(r)

    if len(by_cat) > 1:
        print(f"\nBY CATEGORY:")
        for cat, cat_results in sorted(by_cat.items()):
            n = len(cat_results)
            h = sum(1 for r in cat_results if r.heading_match)
            o = sum(1 for r in cat_results if r.outcome_match)
            fc = sum(1 for r in cat_results if r.false_confidence)
            print(f"  {cat:<24} HD: {h}/{n} ({h/n*100:.0f}%)   OUT: {o}/{n} ({o/n*100:.0f}%)   FC: {fc}")

    by_diff: Dict[str, List[CaseResult]] = defaultdict(list)
    for r in results:
        by_diff[r.difficulty].append(r)

    if len(by_diff) > 1:
        print(f"\nBY DIFFICULTY:")
        for diff, diff_results in sorted(by_diff.items()):
            n = len(diff_results)
            h = sum(1 for r in diff_results if r.heading_match)
            o = sum(1 for r in diff_results if r.outcome_match)
            print(f"  {diff:<10} HD: {h}/{n} ({h/n*100:.0f}%)   OUT: {o}/{n} ({o/n*100:.0f}%)")

    print("=" * 100)


if __name__ == "__main__":
    main()
