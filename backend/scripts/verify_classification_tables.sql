-- SQL Queries to Verify Classification Engine Data Insertion
-- Run these after calling POST /api/v1/classification/generate

-- 1. Count total classification_alternatives
SELECT COUNT(*) as total_alternatives FROM classification_alternatives;

-- 2. Count total classification_audit records
SELECT COUNT(*) as total_audit_records FROM classification_audit;

-- 3. View recent audit records with top candidates
SELECT
    ca.id,
    LEFT(ca.input_description, 50) as description,
    ca.input_coo as coo,
    ca.top_candidate_hts,
    ca.top_candidate_score,
    ca.candidates_generated,
    ca.processing_time_ms,
    ca.created_at
FROM classification_audit ca
ORDER BY ca.created_at DESC
LIMIT 10;

