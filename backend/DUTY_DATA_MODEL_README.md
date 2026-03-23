# Duty Data Model - Sprint 5 Phase 1

## Overview

The `DutyRate` model is a comprehensive, lossless data structure for storing HTS duty rates. It preserves all legal meaning in a format that is both machine-processable and human-auditable.

**Core Principle**: Never discard legal text. Store structure even if not computable.

---

## Model Components

### 1. Enums

#### `DutyType`
Classification of duty rate structure:
- `AD_VALOREM`: Percentage-based (e.g., "4.9%")
- `SPECIFIC`: Per-unit amount (e.g., "$0.50/kg")
- `COMPOUND`: Combination of ad valorem + specific (e.g., "4.9% + $0.50/kg")
- `CONDITIONAL`: Rate depends on conditions (e.g., "See subheading 1234.56.78")
- `FREE`: No duty (e.g., "Free")
- `TEXT_ONLY`: Cannot be parsed but text preserved (e.g., "As provided for in Note 2")

#### `DutyConfidence`
Confidence level in duty rate interpretation:
- `HIGH`: Parsed with high certainty (e.g., clear "4.9%" or "Free")
- `MEDIUM`: Parsed but some ambiguity (e.g., compound rate structure inferred)
- `LOW`: Text preserved but parsing uncertain (e.g., conditional/see reference)

#### `DutySourceLevel`
Source HTS code precision level:
- `SIX_DIGIT`: 6-digit heading level (e.g., "8518.30")
- `EIGHT_DIGIT`: 8-digit subheading level (e.g., "8518.30.10")
- `TEN_DIGIT`: 10-digit statistical level (e.g., "8518.30.1000")

### 2. Core Fields

#### Required Fields
- `hts_code` (String): HTS code (10 chars max)
- `duty_column` (String): Duty column type ('general', 'special', 'column2')
- `source_level` (Enum): Precision level (6/8/10 digit)
- `duty_type` (Enum): Type classification
- `duty_rate_raw_text` (Text): **Raw legal text (NEVER discarded)**
- `duty_confidence` (Enum): Confidence level (default: MEDIUM)
- `is_free` (Boolean): Explicit "Free" flag (default: false)

#### Computable Fields
- `duty_rate_numeric` (Numeric 10,6): Numeric value when computable (nullable)
  - For `AD_VALOREM`: percentage as decimal (4.9% → 4.9)
  - For `FREE`: 0.0
  - For `SPECIFIC`: amount per unit (not final duty)
  - For `COMPOUND`/`CONDITIONAL`/`TEXT_ONLY`: NULL (requires calculation/resolution)

#### Structured Interpretation
- `duty_rate_structure` (JSONB): Structured representation of the duty
  - Flexible JSON structure depends on `duty_type`
  - Examples below

#### Inheritance & Provenance
- `duty_inheritance_chain` (JSONB): Array of HTS codes in inheritance order
  - Example: `["8518", "8518.30", "8518.30.10", "8518.30.1000"]`
  - Enables full audit trail: "This rate came from 8518 heading, inherited to..."

#### Metadata
- `source_page` (String): Page number from HTS PDF
- `effective_from` (DateTime): Effective date range start
- `effective_to` (DateTime): Effective date range end
- `trade_program_info` (JSONB): Trade program / country-specific info
- `additional_metadata` (JSONB): Extensible metadata (parse method, special conditions, etc.)

---

## Example Duty Records

### Example 1: Free Duty

**Raw Text**: "Free"

**Record**:
```python
{
    "hts_code": "8518301000",
    "duty_column": "general",
    "source_level": "ten_digit",
    "duty_type": "free",
    "duty_rate_raw_text": "Free",
    "duty_rate_structure": {
        "is_free": true
    },
    "duty_rate_numeric": 0.0,
    "duty_confidence": "high",
    "is_free": true,
    "duty_inheritance_chain": ["8518", "8518.30", "8518.30.10", "8518.30.1000"],
    "source_page": "HTS-2025-85-12"
}
```

**Key Points**:
- `is_free = true` (first-class flag)
- `duty_rate_numeric = 0.0` (computable)
- `duty_confidence = high` (clear "Free" text)
- Structure preserves intent explicitly

---

### Example 2: Ad Valorem Duty

**Raw Text**: "4.9%"

**Record**:
```python
{
    "hts_code": "8518301000",
    "duty_column": "general",
    "source_level": "ten_digit",
    "duty_type": "ad_valorem",
    "duty_rate_raw_text": "4.9%",
    "duty_rate_structure": {
        "percentage": 4.9
    },
    "duty_rate_numeric": 4.9,
    "duty_confidence": "high",
    "is_free": false,
    "duty_inheritance_chain": ["8518", "8518.30", "8518.30.10", "8518.30.1000"],
    "source_page": "HTS-2025-85-12"
}
```

**Key Points**:
- Numeric value directly computable
- Structure preserves percentage as number
- High confidence (clear format)

---

### Example 3: Compound Duty

**Raw Text**: "4.9% + $0.50/kg"

**Record**:
```python
{
    "hts_code": "8518301000",
    "duty_column": "general",
    "source_level": "ten_digit",
    "duty_type": "compound",
    "duty_rate_raw_text": "4.9% + $0.50/kg",
    "duty_rate_structure": {
        "components": [
            {
                "type": "ad_valorem",
                "percentage": 4.9
            },
            {
                "type": "specific",
                "amount": 0.50,
                "unit": "kg",
                "currency": "USD"
            }
        ]
    },
    "duty_rate_numeric": null,  # Cannot compute without quantity
    "duty_confidence": "high",
    "is_free": false,
    "duty_inheritance_chain": ["8518", "8518.30", "8518.30.10", "8518.30.1000"],
    "source_page": "HTS-2025-85-12"
}
```

**Key Points**:
- `duty_rate_numeric = null` (requires quantity + value for calculation)
- Structure preserves all components
- Still high confidence (components clearly identified)
- **Raw text preserved** (never discarded)

**Calculation Note**: 
To compute duty for this compound rate:
```
duty = (entered_value * 0.049) + (quantity_kg * 0.50)
```

---

### Example 4: Text-Only Duty

**Raw Text**: "As provided for in Note 2 to Chapter 85"

**Record**:
```python
{
    "hts_code": "8518301000",
    "duty_column": "general",
    "source_level": "ten_digit",
    "duty_type": "text_only",
    "duty_rate_raw_text": "As provided for in Note 2 to Chapter 85",
    "duty_rate_structure": {
        "text": "As provided for in Note 2 to Chapter 85",
        "reference_type": "chapter_note",
        "reference": "Note 2 to Chapter 85"
    },
    "duty_rate_numeric": null,  # Cannot compute - requires external resolution
    "duty_confidence": "low",
    "is_free": false,
    "duty_inheritance_chain": ["8518", "8518.30", "8518.30.10", "8518.30.1000"],
    "source_page": "HTS-2025-85-12",
    "additional_metadata": {
        "requires_resolution": true,
        "resolution_source": "chapter_notes"
    }
}
```

**Key Points**:
- `duty_rate_numeric = null` (requires external resolution)
- Low confidence (cannot parse into computable structure)
- **Raw text preserved** (critical for audit trail)
- Structure attempts to extract reference but preserves original text

---

### Example 5: Conditional Duty

**Raw Text**: "See subheading 1234.56.78"

**Record**:
```python
{
    "hts_code": "8518301000",
    "duty_column": "general",
    "source_level": "ten_digit",
    "duty_type": "conditional",
    "duty_rate_raw_text": "See subheading 1234.56.78",
    "duty_rate_structure": {
        "condition_type": "subheading_reference",
        "reference": "1234.56.78",
        "reference_type": "subheading"
    },
    "duty_rate_numeric": null,  # Requires resolution to referenced subheading
    "duty_confidence": "medium",
    "is_free": false,
    "duty_inheritance_chain": ["8518", "8518.30", "8518.30.10", "8518.30.1000"],
    "source_page": "HTS-2025-85-12",
    "additional_metadata": {
        "requires_resolution": true,
        "resolution_target": "1234.56.78"
    }
}
```

**Key Points**:
- `duty_rate_numeric = null` (requires resolution)
- Medium confidence (reference identified but not resolved)
- Structure captures the condition type and reference
- **Raw text preserved** for auditability

---

## Inheritance Chain Example

The `duty_inheritance_chain` field enables full auditability:

**Scenario**: HTS code `8518301000` inherits from:
1. Heading `8518` (6-digit): "Free"
2. Subheading `8518.30` (8-digit): "4.9%"
3. Statistical suffix `8518.30.10` (10-digit): "4.9%"
4. Final code `8518.30.1000` (10-digit): "4.9%"

**Record**:
```python
{
    "hts_code": "8518301000",
    "duty_inheritance_chain": ["8518", "8518.30", "8518.30.10", "8518.30.1000"],
    "duty_rate_raw_text": "4.9%",
    "source_level": "ten_digit",
    # ... other fields
}
```

**Audit Trail**:
- "This duty rate was inherited from heading 8518 (Free), then from subheading 8518.30 (4.9%), then from statistical suffix 8518.30.10 (4.9%), and finally confirmed at 8518.30.1000 (4.9%)."
- A regulator can see the full path and verify correctness.

---

## Design Principles

### 1. Lossless Storage
- **Raw text is NEVER discarded** (`duty_rate_raw_text` is required)
- Even if structured interpretation fails, original text is preserved

### 2. Computability vs. Representation
- If computable → store numeric (`duty_rate_numeric`)
- If not computable → store structure (`duty_rate_structure`)
- Both → store both (redundancy for auditability)

### 3. "Free" is First-Class
- `is_free = true` (explicit boolean flag)
- `duty_rate_numeric = 0.0` (not NULL)
- `duty_type = FREE` (type classification)
- **Never infer "Free" from NULL numeric**

### 4. Inheritance Chain Auditability
- Every duty rate can explain where it came from
- Chain is JSONB array (flexible, queryable)
- Enables full audit trail for CBP compliance

### 5. Confidence Levels
- `HIGH`: Clear, unambiguous parsing
- `MEDIUM`: Parsed but some inference required
- `LOW`: Text preserved but not computable

---

## Usage Patterns

### Query: Get all free duties for an HTS code
```sql
SELECT * FROM duty_rates 
WHERE hts_code = '8518301000' 
AND is_free = true;
```

### Query: Get highest confidence duty for an HTS code
```sql
SELECT * FROM duty_rates 
WHERE hts_code = '8518301000' 
AND duty_column = 'general'
ORDER BY 
    CASE duty_confidence 
        WHEN 'high' THEN 1 
        WHEN 'medium' THEN 2 
        WHEN 'low' THEN 3 
    END
LIMIT 1;
```

### Query: Find all compound duties
```sql
SELECT * FROM duty_rates 
WHERE duty_type = 'compound';
```

### Query: Get inheritance chain for an HTS code
```sql
SELECT duty_inheritance_chain, duty_rate_raw_text
FROM duty_rates
WHERE hts_code = '8518301000'
ORDER BY source_level DESC;
```

---

## Sprint 5 Phase 1 Status

✅ **Complete**:
- Model definition (`DutyRate`)
- Enum definitions (`DutyType`, `DutyConfidence`, `DutySourceLevel`)
- Alembic migration (`005_add_duty_rates_table.py`)
- Example records (Free, Ad valorem, Compound, Text-only, Conditional)

⏭️ **Next Steps** (Sprint 5 Phase 2):
- Duty parsing engine (lossless)
- Duty inheritance engine
- Duty calculation engine (deterministic)
- Duty explainability layer

---

## Compliance Note

**Sprint 5 Hard Stop Criterion**: 
> "If you can't explain a duty to a CBP auditor, Sprint 5 is not done."

This model ensures:
- Every duty has raw text (what CBP says)
- Every duty has structure (what we interpreted)
- Every duty has inheritance chain (where it came from)
- Every duty has confidence level (how certain we are)
- Every "Free" is explicit (not inferred from NULL)

**The model is auditor-ready. The parsing engine (Phase 2) must populate it correctly.**
