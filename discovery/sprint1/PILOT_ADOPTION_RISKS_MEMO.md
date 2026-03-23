# Pilot Adoption Risks Memo (Sprint 1 Draft)

Owner: Phil  
Date: February 19, 2026  
Status: Draft for evidence validation in active interviews

## Purpose

Define the highest-likelihood adoption risks to validate this sprint, centered on trust blockers, must-have outputs, and onboarding friction.

## Risk 1: Insufficient Trust Signals in Analysis Output

- Risk statement: Users may not trust analysis results without transparent rationale, source mapping, and clear refusal logic.
- Category: Trust blocker
- KPI impact hypothesis:
  - Pilot path completion rate: down
  - Review outputs generated: down
  - Non-deterministic output incident perception: up
- Evidence required:
  - Three or more repeated quotes on trust requirements across at least two segments
  - Specific missing output components named by users

## Risk 2: Missing Must-Have Review Output Fields

- Risk statement: If outputs do not include required review artifacts, teams will not adopt for production-adjacent workflows.
- Category: Must-have outputs
- KPI impact hypothesis:
  - Review outputs generated: down
  - Export success rate: down
  - Time-to-first-analysis adoption conversion: down
- Evidence required:
  - Ranked must-have output list by persona
  - Frequency count for each output requirement

## Risk 3: Broker Handoff Breaks from Upstream Data Gaps

- Risk statement: Poor data completeness at importer stage drives broker rework and rejection.
- Category: Must-have outputs and trust blocker
- KPI impact hypothesis:
  - Failed analyses: up
  - Broker-prep exports generated: down
  - Export success rate: down
- Evidence required:
  - Broker examples of handoff failure
  - Importer workflows where data quality fails

## Risk 4: Onboarding Burden Exceeds Segment Tolerance

- Risk statement: Setup effort may be perceived as too high, especially for SMB teams and constrained importer teams.
- Category: Onboarding friction
- KPI impact hypothesis:
  - Interview-to-pilot conversion: down
  - Median time-to-first-analysis: up
- Evidence required:
  - Minimum acceptable setup benchmark by persona
  - Top onboarding objections with frequency

## Risk 5: Segment Contradictions Drive Scope Drift

- Risk statement: Conflicting segment requirements may cause undisciplined scope expansion beyond the pilot path.
- Category: Cross-segment risk
- KPI impact hypothesis:
  - Sprint completion rate: down
  - Blocked items: up
  - Scope changes without KPI benefit: up
- Evidence required:
  - Contradiction matrix across importer, broker, SMB
  - Explicit pilot-critical vs nice-to-have tagging

## Evidence Threshold for Recommendation Readiness

No recommendation is considered decision-grade until all are true:
- At least three interviews completed in primary segment
- At least one broker and one SMB interview completed
- Attributable quote support for risk and recommendation
- KPI impact statement with expected direction and confidence

## End-of-Week Decision Output Format

- `Now`: pilot-critical, evidence-backed items only
- `Next`: high-confidence but non-blocking improvements
- `Later`: nice-to-have or low-confidence items
