# NECO Sprint 0 Charter (Reset Baseline)

Owner: Steven  
Strategy Owner: Ben  
Date: February 19, 2026  
Status: ACTIVE

## Purpose

Establish a single source of truth for what NECO is, what has been built, what is in scope now, and how decisions are made.

## Product North Star

NECO is a customs compliance and analysis platform that helps importers and brokers improve compliance quality and reduce duty leakage risk through structured shipment and document workflows and auditable outputs.

## 90-Day Goal

Launch and test NECO's pilot program with end-to-end compliance-analysis workflows.

Out of scope for this 90-day window:
- PSC filing execution
- Entry/import filing execution

## Primary Users

- Import Compliance leaders (Director, Manager, VP) at U.S. importers
- Customs brokers
- SMB import owners (secondary segment)

## Current-State Baseline (Repo-Evidenced)

- Core backend, auth, data models, ingestion, and document analysis are implemented.
- Sprint 12 foundation for org/shipments/analysis is partially complete.
- Key workflow components remain to be completed and hardened for pilot reliability.
- Discovery and QA operating functions are now formalized (Phil and Dean).

## Pilot Path (Must Work End-to-End)

1. Create shipment
2. Upload required documents
3. Run analysis with eligibility/refusal gating
4. Produce review output
5. Generate broker-prep export with blocker enforcement

## Definition of Pilot-Ready

- 3 real sample shipments processed end-to-end
- Zero cross-org leakage defects
- Deterministic outputs for review and export
- QA GO recommendation (Dean)

## Agent Roles

- Steven: final decision authority, orchestration
- Ben (Strategy): scope guardrails, sprint planning, prioritization, KPI governance
- Oliver (Builder): implementation owner for pilot critical path
- Dean (QA): release gate, defect severity governance, go/no-go
- Phil (Discovery): customer evidence engine and weekly pattern reporting

## Decision Rules

- No sprint item without direct pilot-path relevance or KPI impact.
- Ambiguous compliance logic is escalated, not silently inferred.
- Reliability and auditability take priority over breadth.

## Cadence

- Monday: scope lock and sprint plan
- Wednesday: risk and de-scope review
- Friday: demo, KPI review, and next sprint draft
