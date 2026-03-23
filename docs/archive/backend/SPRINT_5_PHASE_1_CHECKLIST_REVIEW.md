# Sprint 5 Phase 1 - Checklist Review ✅

## Hard Rule: No Duty Meaning Loss

### ✅ Raw Text Stores Exact HTS Wording
- **Field**: `duty_rate_raw_text` (Text, NOT NULL)
- **Documentation**: "Stores the EXACT wording from HTS source document, verbatim. No normalization, no cleaning, no abbreviation expansion."
- **Status**: ✅ PASS - Raw text is never cleaned or normalized

### ✅ Free is First-Class
- **Fields**: 
  - `is_free` (Boolean, NOT NULL, default=False, indexed)
  - `duty_rate_numeric = 0.0` for free duties (not NULL)
  - `duty_type = FREE`
- **Documentation**: "Note: 'Free' can be conditional (e.g., 'Free (See subheading...)'). is_free = True does NOT imply HIGH confidence - check duty_confidence separately."
- **Status**: ✅ PASS - Free is explicit, conditional free supported

### ✅ DutySourceLevel + Actual Code String
- **Fields**:
  - `source_level` (Enum: SIX_DIGIT, EIGHT_DIGIT, TEN_DIGIT, indexed)
  - `source_code` (String(10), NOT NULL, indexed) - **the actual 6/8/10 digit code string**
- **Status**: ✅ PASS - Both level enum and actual code string stored

### ✅ Enhanced Inheritance Chain
- **Field**: `duty_inheritance_chain` (JSONB, nullable)
- **Format**: Array of objects with full metadata:
  ```json
  [
    {
      "from_code": "8518",
      "from_level": "six_digit",
      "reason": "heading_rate",
      "timestamp": "2025-01-01T00:00:00",
      "hts_version_id": "uuid-or-null"
    },
    ...
  ]
  ```
- **Captures**: from_code, from_level, reason, timestamp, source_document/version_id
- **Status**: ✅ PASS - Full provenance for each inheritance step

### ✅ Required Indexes
- **hts_code**: ✅ `ix_duty_rates_hts_code`
- **effective_date range**: ✅ `ix_duty_rates_effective_start_date`, `ix_duty_rates_effective_end_date`
- **source_level**: ✅ `ix_duty_rates_source_level`
- **duty_type**: ✅ `ix_duty_rates_duty_type`
- **Additional**: `hts_version_id`, `source_code`, `duty_column`, `duty_confidence`, `is_free` all indexed
- **Status**: ✅ PASS - All required indexes present

### ✅ Time Context (Critical for PSC)
- **Fields**:
  - `hts_version_id` (UUID, nullable, indexed) - FK to hts_versions table
  - `effective_start_date` (DateTime, nullable, indexed)
  - `effective_end_date` (DateTime, nullable, indexed)
- **Documentation**: "Enables historical duty comparisons and PSC eligibility checks"
- **Status**: ✅ PASS - Full time context available

### ✅ Unit Normalization for Specific Duties
- **Fields in `duty_rate_structure` for SPECIFIC/COMPOUND**:
  - `unit`: Original unit from text (kg, no, m2, etc.)
  - `unit_normalized`: Normalized unit code (kg, g, m, cm, pcs, m2, etc.)
  - `quantity_basis`: "net_weight", "gross_weight", "units", "area", "volume", etc.
- **Status**: ✅ PASS - Normalized unit fields included

## Summary

**All checklist items PASS** ✅

The model is hardened and ready for Phase 2 (Duty Parsing Engine).

### Key Hardening Changes Made:
1. ✅ Raw text explicitly documented as verbatim (no cleaning)
2. ✅ Free flag clarified - does not imply HIGH confidence (conditional free supported)
3. ✅ `source_code` field added (actual 6/8/10 digit string)
4. ✅ Inheritance chain enhanced to objects with full metadata (from_code, from_level, reason, timestamp, hts_version_id)
5. ✅ Time context fields documented (`hts_version_id`, `effective_start_date`, `effective_end_date`)
6. ✅ Unit normalization fields updated (`quantity_basis` uses net_weight/gross_weight/units/area/volume, not just per_unit/per_100)
7. ✅ Summary document updated to reflect all fields

### Ready for Phase 2:
- ✅ Model is lossless
- ✅ Time context is complete
- ✅ Inheritance chain is auditable
- ✅ Unit normalization is explicit
- ✅ All indexes are in place
