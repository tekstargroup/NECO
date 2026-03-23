# How to Run Classification Engine

## Overview

The Classification Engine (Sprint 3) generates alternative HTS codes for products using text similarity search against the HTSUS tariff schedule.

## Prerequisites

1. **Database must be running (PostgreSQL)**
   ```bash
   # Start database using Docker Compose
   cd /Users/stevenbigio/Cursor\ Projects/NECO
   docker-compose up -d
   
   # Verify database is running
   docker ps | grep postgres
   # Should show: neco_postgres container running
   ```

2. **HTS data must be ingested (2025HTS.pdf)**
   - Check: `GET /api/v1/health/knowledge-base`
   - Should show HTS records > 0

3. **Server must be running** (optional for smoke test, required for API)
   ```bash
   ./start_neco.sh
   # Or
   cd backend && uvicorn app.main:app --reload
   ```

## API Endpoints

### 1. Generate Classification Alternatives

**Endpoint:** `POST /api/v1/classification/generate`

**Authentication:** Required (Bearer token)

**Request Body:**
```json
{
  "description": "Wireless Bluetooth earbuds with charging case",
  "country_of_origin": "CN",
  "value": 25.99,
  "quantity": 100,
  "current_hts_code": "8518.12.0000",
  "sku_id": "optional-sku-uuid"
}
```

**cURL Example:**
```bash
# First, get a token (register/login)
TOKEN=$(curl -X POST "http://localhost:9000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your@email.com",
    "password": "yourpassword"
  }' | jq -r '.access_token')

# Generate classification
curl -X POST "http://localhost:9000/api/v1/classification/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Wireless Bluetooth earbuds with charging case",
    "country_of_origin": "CN",
    "value": 25.99,
    "quantity": 100
  }'
```

**Response:**
```json
{
  "success": true,
  "candidates": [
    {
      "hts_code": "8518.12.0000",
      "hts_chapter": "85",
      "tariff_text_short": "Headphones, earphones...",
      "similarity_score": 0.75,
      "final_score": 0.82,
      "selected_rate_type": "general",
      "selected_rate": "3.5%",
      "duty_rate_numeric": 3.5,
      "parse_confidence": "high",
      "source_page": 1234
    },
    ...
  ],
  "metadata": {
    "engine_version": "v1.0",
    "processing_time_ms": 245,
    "total_candidates_found": 8,
    "top_candidate_hts": "8518.12.0000",
    "top_candidate_score": "0.820"
  }
}
```

### 2. Get Alternatives for SKU

**Endpoint:** `GET /api/v1/classification/{sku_id}/alternatives`

**Authentication:** Required (Bearer token)

**cURL Example:**
```bash
curl -X GET "http://localhost:9000/api/v1/classification/123e4567-e89b-12d3-a456-426614174000/alternatives" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "sku_id": "123e4567-e89b-12d3-a456-426614174000",
  "sku_description": "Wireless Bluetooth earbuds",
  "alternatives": [
    {
      "id": "alt-uuid",
      "alternative_hts": "8518.12.0000",
      "confidence_score": 0.82,
      "risk_score": 3,
      "alternative_duty": 3.5,
      "current_duty": null,
      "duty_difference": null,
      "is_recommended": 2,
      "justification": "Similarity: 0.75, Final Score: 0.820",
      "created_at": "2026-01-08T12:00:00"
    },
    ...
  ]
}
```

## Testing

### Smoke Test Script

**IMPORTANT: Database must be running before running smoke test!**

```bash
# 1. Start database (if not already running)
cd /Users/stevenbigio/Cursor\ Projects/NECO
docker-compose up -d

# 2. Wait a few seconds for database to be ready
sleep 5

# 3. Run smoke test
cd backend
python3 scripts/smoke_test_classification.py
```

If you see "Connect call failed" errors, the database is not running. Start it with `docker-compose up -d`.

This will test 3 sample products:
1. Wireless Bluetooth earbuds (COO: CN)
2. Cotton t-shirt (COO: MX)
3. Stainless steel kitchen knife set (COO: DE)

### Manual Testing

1. **Start the server:**
   ```bash
   ./start_neco.sh
   # Or
   cd backend && uvicorn app.main:app --reload
   ```

2. **Register/Login to get token:**
   ```bash
   # Register
   curl -X POST "http://localhost:9000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "testpass123",
       "company_name": "Test Company",
       "importer_number": "12-3456789"
     }'
   
   # Login
   TOKEN=$(curl -X POST "http://localhost:9000/api/v1/auth/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "testpass123"
     }' | jq -r '.access_token')
   ```

3. **Test classification:**
   ```bash
   curl -X POST "http://localhost:9000/api/v1/classification/generate" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "description": "Wireless Bluetooth earbuds with charging case",
       "country_of_origin": "CN",
       "value": 25.99
     }' | jq
   ```

## How It Works

1. **Candidate Generation:**
   - Searches `hts_versions` table (2025HTS.pdf ingest only)
   - Uses text similarity (pg_trgm if available, else LIKE + Python ranking)
   - Filters out chapters 98/99 and codes starting with 9903
   - Returns top 10 candidates

2. **Scoring:**
   - Similarity score (60% weight)
   - Parse confidence penalty (if not "high")
   - Duty rate general penalty (if COO is MFN and general missing)
   - Special countries bonus (if COO eligible for Free rate)
   - Current HTS match bonus (if provided)

3. **Duty Selection:**
   - If COO in `special_countries` and special rate is "Free" → use special
   - If COO is non-MFN (KP, CU) → use column2
   - Otherwise → use general (MFN)

4. **Persistence:**
   - Saves candidates to `classification_alternatives` table
   - Saves audit trail to `classification_audit` table
   - Stores context payload, provenance, and metadata

## Database Tables

### classification_alternatives
Stores generated HTS code alternatives with scores, duty rates, and recommendations.

### classification_audit
Stores audit trail with:
- Input data (description, COO, value, etc.)
- Context payload (from ClassificationContextBuilder)
- Provenance (source pages, code IDs)
- Processing metadata

## Troubleshooting

1. **No candidates found:**
   - Check if HTS data is ingested: `GET /api/v1/health/knowledge-base`
   - Verify description is not too generic
   - Check database connection

2. **pg_trgm not available:**
   - Engine falls back to LIKE + Python ranking
   - Performance may be slower but functionality works

3. **Authentication errors:**
   - Ensure token is valid and not expired
   - Check token format: `Bearer <token>`

4. **Database errors:**
   - Ensure PostgreSQL is running
   - Check database migrations are applied
   - Verify `classification_audit` table exists

## Next Steps

- Integrate with PSC Radar (Sprint 4)
- Add LLM-based reasoning (future enhancement)
- Improve similarity search with embeddings
- Add CROSS rulings integration

