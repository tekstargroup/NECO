# PSC Radar Documentation - Sprint 6

## Purpose

PSC Radar is a **read-only intelligence MVP** that surfaces classification-driven risk signals for broker and compliance review.

**CRITICAL DISCLAIMER:**
- **NECO does NOT recommend filing PSCs (Prior Disclosure Corrections)**
- **NECO does NOT provide filing advice**
- **NECO does NOT automate PSC filing workflows**
- **PSC Radar is an early-warning system, NOT an action system**

## What PSC Radar Does

PSC Radar identifies when:
- An alternative plausible HTS classification exists
- The alternative carries a materially different general duty rate
- Historical classification patterns differ from current declaration

## What PSC Radar Does NOT Do

PSC Radar explicitly does NOT:
- Recommend filing a PSC
- Provide legal advice
- Calculate potential savings or refunds
- Assess PSC eligibility
- Consider trade program eligibility
- Evaluate country-specific rates beyond general duty
- Consider quota or safeguard logic
- Provide risk scores beyond simple flags
- Suggest specific actions

## Input Contract

PSC Radar accepts:
- `product_description` (string, required)
- `declared_hts_code` (10-digit string, required)
- `quantity` (numeric, required)
- `customs_value` (numeric, required)
- `country_of_origin` (string, optional - used only for math context)
- `historical_entries` (list, optional - user-provided only)

**No OCR. No ACE ingestion. No guessing missing inputs.**

## Output Contract

PSC Radar returns:
- **Neutral, conservative signals** only
- **Factual duty delta information** (percentage points and dollar amounts)
- **Flags** indicating material differences
- **Legal anchor references** (chapter/heading)
- **No recommendations**
- **No confidence scores**
- **No "recommended action"**

## Example Output

```
"This classification may warrant review because an alternative HTS code 
within the same product family carries a materially different general duty rate. 
Alternative 6112.20.10.10 has a general duty rate of 28.2% (vs. declared 8.3%), 
representing a 19.9 percentage point difference and $9,950.00 in duty impact. 
No filing recommendation is made."
```

## Flags

PSC Radar uses the following flags:
- `DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD`: Duty difference exceeds percentage threshold (default: 2.0%)
- `DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD`: Duty difference exceeds dollar threshold (default: $1,000)
- `DIFFERENT_CHAPTER_USED_HISTORICALLY`: Historical entries used different chapter
- `DIFFERENT_HEADING_USED_HISTORICALLY`: Historical entries used different heading
- `DUTY_RATE_CHANGED_FROM_HISTORY`: Duty rate differs from historical pattern

## Usage

```python
from app.engines.psc_radar import PSCRadar

radar = PSCRadar(db_session)
result = await radar.analyze(
    product_description="Women's cotton knit sweater",
    declared_hts_code="6112.20.20.30",
    quantity=100,
    customs_value=50000.0,
    country_of_origin="CN"
)

# Check flags
if PSCRadarFlag.DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD in result.flags:
    # Signal surfaced - broker should review
    print(result.summary)
```

## Hard Rules

1. **Read-only**: No mutation of HTS data
2. **No new heuristics**: Reuses existing classification engine output
3. **General duty only**: No trade programs, no netting, no refunds
4. **Must not break golden tests**: If Sprint 6 breaks a golden test, STOP

## Integration with Classification Engine

PSC Radar:
- Uses existing `ClassificationEngine.generate_alternatives()` output
- Does NOT re-rank classification logic
- Filters alternatives to same product family OR same chapter/heading
- Limits to top 2-3 alternatives

## Integration with Duty Resolver

PSC Radar:
- Uses `DUTY_RESOLVER_V1` (from `scripts.duty_resolution.resolve_duty()`)
- Resolves general duty only (no special, no column 2)
- Uses authoritative HTS version (`AUTHORITATIVE_HTS_VERSION_ID`)

## Exit Criteria

Sprint 6 is complete when:
1. Given a declared HTS code, the system can:
   - Show 1-3 plausible alternatives
   - Show duty deltas
   - State factual structural differences (codes differ at chapter/heading/subheading, duties differ accordingly)
2. A broker reads the output and says:
   - "Yes, this is something I'd want to look at."
   - NOT: "You're telling me to file a PSC."

**Note**: PSC Radar states structural facts only. It does not explain legal causality or "why" beyond the fact that codes differ at different HTS levels and duties differ accordingly.

## Next Steps (Sprint 7+)

PSC Radar is **read-only intelligence**. Future sprints may include:
- Review workflows
- Enrichment with additional signals
- User interface for reviewing signals

**Do NOT extend Sprint 6 scope to include filing workflows or recommendations.**
