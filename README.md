# NECO - Next-Gen Compliance Engine

NECO is an AI-powered customs compliance platform that automates HS classification, PSC opportunities, and regulatory intelligence.

**Full project status:** See [PROJECT_STATUS.md](PROJECT_STATUS.md) for what's built and what remains.

---

## 📊 **Sprint 1: Foundation - COMPLETE**

### ✅ What's Built

```
✅ Project structure and architecture
✅ Docker Compose (PostgreSQL + Redis)
✅ FastAPI backend with authentication (JWT)
✅ Database models (Client, User, SKU, Entry, LineItem, etc.)
✅ Document ingestion engine:
   • PDF extraction (pdfplumber)
   • Excel parsing (pandas)
   • Intelligent field detection (Claude AI)
   • Commercial Invoice processor
   • Entry Summary processor
✅ API endpoints:
   • /api/v1/auth/login
   • /api/v1/auth/register
   • /api/v1/auth/me
   • /api/v1/documents/upload
   • /api/v1/documents
   • /api/v1/documents/{id}
✅ Health check endpoints
```

---

## 🚀 **Quick Start**

### **Step 1: Set Up Environment**

```bash
cd "/Users/stevenbigio/Cursor Projects/NECO"

# Copy environment template
cp env.example .env

# Edit .env and add your Anthropic API key
nano .env
# Set: ANTHROPIC_API_KEY=your_key_here

# Generate a secure SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Add the result to .env as SECRET_KEY
```

### **Step 2: Start NECO**

```bash
./start_neco.sh
```

This will:
- Start Docker containers (PostgreSQL + Redis)
- Create Python virtual environment (if needed)
- Install dependencies
- Start the FastAPI server (port 9000 or 9001 per config)

### **Step 3: Access NECO**

- **API Base:** http://localhost:9001 (or 9000 if using default)
- **API Docs:** http://localhost:9001/docs (Interactive Swagger UI)
- **Health Check:** http://localhost:9001/health

---

## 📝 **Testing Sprint 1**

### **1. Register a Client**

```bash
curl -X POST "http://localhost:9001/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Company",
    "importer_number": "12-3456789",
    "admin_email": "admin@test.com",
    "admin_password": "secure_password123",
    "admin_full_name": "Admin User"
  }'
```

### **2. Login**

```bash
curl -X POST "http://localhost:9001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@test.com",
    "password": "secure_password123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {...}
}
```

**Save the access_token!**

### **3. Upload a Document**

```bash
# Using your access token from step 2
curl -X POST "http://localhost:9001/api/v1/documents/upload" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -F "file=@/path/to/invoice.pdf"
```

**Expected Response:**
```json
{
  "document_id": "uuid-here",
  "filename": "invoice.pdf",
  "document_type": "commercial_invoice",
  "processing_status": "completed",
  "confidence_score": 85,
  "structured_data": {
    "po_number": "608671",
    "country_of_origin": "CN",
    "total_value": 45232.00,
    "line_items": [...]
  },
  "message": "Document uploaded and processed successfully"
}
```

### **4. Test with Real AURA Documents**

```bash
# Upload one of your actual invoices from AURA
TOKEN="your_access_token_here"

curl -X POST "http://localhost:9001/api/v1/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/stevenbigio/Cursor Projects/AURA/Entries:Shipments/CI_608671.pdf"
```

---

## 🏗️ **Architecture**

```
NECO/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # API endpoints
│   │   │   ├── auth.py       # Authentication
│   │   │   └── documents.py  # Document upload
│   │   ├── core/             # Core utilities
│   │   │   ├── config.py     # Configuration
│   │   │   ├── database.py   # Database connection
│   │   │   └── security.py   # JWT & passwords
│   │   ├── models/           # Database models
│   │   │   ├── client.py
│   │   │   ├── user.py
│   │   │   ├── sku.py
│   │   │   ├── entry.py
│   │   │   ├── classification.py
│   │   │   ├── psc_opportunity.py
│   │   │   └── document.py
│   │   ├── engines/          # Processing engines
│   │   │   └── ingestion/
│   │   │       ├── pdf_extractor.py
│   │   │       ├── excel_parser.py
│   │   │       ├── field_detector.py
│   │   │       └── document_processor.py
│   │   └── main.py           # FastAPI app
│   └── requirements.txt
├── data/                     # Uploads & vector store
├── docker-compose.yml        # PostgreSQL + Redis
├── start_neco.sh            # Startup script
└── .env                      # Configuration
```

---

## 🧪 **What Works Now**

### **Document Ingestion**
- ✅ PDF text extraction
- ✅ PDF table extraction
- ✅ Excel/CSV parsing
- ✅ Document type detection (CI, ES, etc.)
- ✅ Commercial Invoice field extraction
- ✅ Entry Summary field extraction
- ✅ Claude AI-powered intelligent parsing

### **Extracted Data from Commercial Invoice:**
```json
{
  "po_number": "608671",
  "invoice_number": "INV-2024-001",
  "country_of_origin": "CN",
  "incoterm": "FOB",
  "total_value": 45232.00,
  "currency": "USD",
  "supplier_name": "Shenzhen Manufacturing Co",
  "line_items": [
    {
      "line_number": 1,
      "description": "Wireless Bluetooth earbuds",
      "quantity": 100,
      "unit": "pairs",
      "unit_price": 23.50,
      "total": 2350.00,
      "hts_code": null
    }
  ]
}
```

### **Extracted Data from Entry Summary:**
```json
{
  "entry_number": "123-4567890-1",
  "entry_type": "01",
  "entry_date": "2024-11-15",
  "port_of_entry": "2704",
  "total_entered_value": 45232.00,
  "total_duty": 11308.00,
  "line_items": [
    {
      "line_number": 1,
      "description": "Wireless Bluetooth earbuds",
      "hts_code": "8517.62.0020",
      "country_of_origin": "CN",
      "entered_value": 2350.00,
      "duty_rate": 0.0,
      "duty_amount": 0.00,
      "section_301_rate": 25.0,
      "section_301_amount": 587.50
    }
  ]
}
```

---

## Next Steps

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for current blockers and post-MVP roadmap.

---

## 🐛 **Troubleshooting**

### **Docker not starting:**
```bash
# Make sure Docker Desktop is running
open -a Docker

# Check if containers are running
docker ps

# Restart containers
docker-compose down
docker-compose up -d
```

### **Database errors:**
```bash
# Reset database
docker-compose down -v
docker-compose up -d

# Wait 5 seconds for DB to initialize
sleep 5
```

### **Import errors:**
```bash
# Make sure you're in the virtual environment
source venv_neco/bin/activate

# Reinstall dependencies
pip install -r backend/requirements.txt
```

### **Port 9001 (or 9000) already in use:**
```bash
# Find what's using the port
lsof -i :9001

# Kill the process
kill -9 <PID>
```

---

## 📊 **Database Schema**

Tables created:
- `clients` - Multi-tenant client companies
- `users` - User accounts with authentication
- `skus` - Product/SKU tracking
- `entries` - Customs entry records
- `line_items` - Entry line items
- `classification_alternatives` - Alternative HTS codes
- `psc_opportunities` - PSC opportunities tracking
- `documents` - Uploaded document tracking

---

## 🎉 **Sprint 1 Success Metrics**

✅ **Infrastructure:** Docker + PostgreSQL + Redis
✅ **Backend:** FastAPI with 8 API endpoints
✅ **Auth:** JWT-based multi-tenant authentication  
✅ **Database:** 8 models with relationships
✅ **Ingestion:** PDF, Excel, AI-powered extraction
✅ **Processing:** Commercial Invoice & Entry Summary parsing
✅ **Time:** Built in ~2.5 hours of focused work

---

## 🚀 **Ready to Test?**

1. Start NECO: `./start_neco.sh`
2. Register a client
3. Login and get token
4. Upload a real invoice from AURA
5. See the magic happen! 🎩✨

---

---

*For full status, see [PROJECT_STATUS.md](PROJECT_STATUS.md).*


