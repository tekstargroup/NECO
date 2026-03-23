-- Add audit replayability fields to classification_audit
ALTER TABLE classification_audit 
ADD COLUMN IF NOT EXISTS applied_filters JSONB;

ALTER TABLE classification_audit 
ADD COLUMN IF NOT EXISTS candidate_counts JSONB;

ALTER TABLE classification_audit 
ADD COLUMN IF NOT EXISTS similarity_top VARCHAR(20);

ALTER TABLE classification_audit 
ADD COLUMN IF NOT EXISTS threshold_used VARCHAR(20);

ALTER TABLE classification_audit 
ADD COLUMN IF NOT EXISTS reason_code VARCHAR(50);

ALTER TABLE classification_audit 
ADD COLUMN IF NOT EXISTS status VARCHAR(50);
