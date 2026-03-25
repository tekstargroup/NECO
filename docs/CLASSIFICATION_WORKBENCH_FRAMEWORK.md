# Classification Workbench Framework (Sprint 14.5)

Purpose: codify a repeatable, auditable classification method for NECO that combines deterministic legal-style rules with model-based ranking.

## 1) Rule Engine (Deterministic)

NECO now includes a rule-based layer in `backend/app/engines/classification/rule_based_classifier.py` and applies it during shipment analysis.

Core rule order:

1. Training/demo only and not used on humans -> `9023.00.00`
2. Used on humans in medical context -> heading `9018`
3. Medical robotics -> prefer `9018` over `8479` fallback
4. Integrated multi-component medical system -> likely `9018.90.75`
5. Direct procedural action inside body -> likely `9018.90.80`
6. Accessory/part without independent action -> `9018.90.xx`
7. Non-medical, non-training fallback -> `8479.xx.xx` (low confidence)

The rule engine produces:
- heading/subheading suggestion
- confidence
- justification bullets
- alternatives considered and rejected
- reasoning path

## 2) Decision Tree (Human Review / SOP)

```text
START
 |
 |-- Q1: Principal function?
 |      |
 |      |-- Training / Demonstration only?
 |      |       |
 |      |       |-- YES
 |      |       |    |
 |      |       |    |-- Q2: Used on humans for diagnosis/treatment?
 |      |       |           |
 |      |       |           |-- NO --> 9023.00.00
 |      |       |           |-- YES --> Reassess (likely not pure 9023)
 |      |
 |      |-- Medical / Surgical use?
 |              |
 |              |-- YES --> Heading 9018 analysis
 |              |-- NO  --> Consider non-medical specific headings; 8479 only fallback
 |
 |-- Q3: Robotic medical system?
 |      |
 |      |-- YES --> Prefer 9018 over 8479 (specificity)
 |
 |-- Q4: Integrated multi-component apparatus?
 |      |
 |      |-- YES --> 9018.90.75 likely
 |      |-- NO  --> continue
 |
 |-- Q5: Direct procedural action + body interaction?
 |      |
 |      |-- YES --> 9018.90.80 likely
 |      |-- NO  --> continue
 |
 |-- Q6: Support-only accessory/part?
 |      |
 |      |-- YES --> 9018.90.xx parts/accessories analysis
 |      |-- NO  --> more facts needed
 |
END
```

## 3) AI Agent Prompt Template

Use this when running an LLM for classification explainability:

```text
You are a U.S. customs classification agent focused on HTSUS analysis.

Task: classify the imported article using a structured legal reasoning process.
Do not jump directly to a tariff number.

Process:
1) Identify article and principal function.
2) Determine if medical/surgical use, training/demo use, part/accessory, or general machinery.
3) Consider candidate headings (at least 9018, 9023, 8479 where relevant).
4) Apply specificity logic (prefer specific medical heading over general machinery).
5) Determine apparatus vs instrument vs part/accessory.
6) Return tentative HTSUS + confidence + rejected alternatives.
7) State missing facts and non-binding legal caution.

Output format:
- Product
- Facts relied on
- Principal function
- Candidate headings considered
- Classification analysis
- Proposed HTSUS
- Confidence
- Alternative headings rejected
- Open issues / facts needed
- Legal caution (non-binding, CBP ruling recommended when material)
```

## 4) How NECO Uses This Today

- Rule engine runs per item after model candidate generation.
- Rule assessment is attached into classification output under `rule_based_assessment`.
- Candidate ranking is biased toward legally preferred heading; when no candidate matches and rule is decisive, an advisory candidate may be injected.

## 5) Non-Binding Caution

This is an analytical framework, not legal advice and not a binding ruling. Final import treatment can depend on:
- intended use and regulatory filings
- import condition (standalone vs set under GRI 3(b))
- transaction-specific facts

