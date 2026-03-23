# 🗺️ NECO Sprint Plan - Complete Roadmap

**Last Updated:** December 29, 2024  
**Current Status:** Sprint 2 Complete ✅ | Ready for Sprint 3 🚀

---

## 📊 **SPRINT OVERVIEW**

| Sprint | Focus | Status | Time | Priority |
|--------|-------|--------|------|----------|
| **Sprint 1** | Foundation & Ingestion | ✅ **COMPLETE** | 2.5h | Critical |
| **Sprint 2** | Intelligent Extraction | ✅ **COMPLETE** | 2.5h | Critical |
| **Sprint 3** | Classification Engine | ⏳ **NEXT** | 3h | **HIGH** 💰 |
| **Sprint 4** | PSC Radar | 📋 Planned | 2.5h | **HIGH** 💰 |
| **Sprint 5** | Frontend Dashboard | 📋 Planned | 4h | Medium |
| **Sprint 6** | Advanced Features | 📋 Planned | 3h | Low |
| **Total** | **Full NECO Platform** | **28% Done** | **18h** | - |

---

## ✅ **SPRINT 1: Foundation & Ingestion (COMPLETE)**

### **Objective:**
Build the core infrastructure and document processing pipeline to extract structured data from trade documents.

### **What Was Built:**

#### **1. Infrastructure Setup**
- ✅ Docker Compose configuration (PostgreSQL 15 + Redis 7)
- ✅ FastAPI backend with async database operations
- ✅ Project structure and architecture
- ✅ Virtual environment setup
- ✅ Configuration management (.env)

#### **2. Authentication System**
- ✅ JWT-based authentication
- ✅ Multi-tenant architecture (client isolation)
- ✅ User registration and login
- ✅ Password hashing (bcrypt)
- ✅ Token management (8-hour expiration)

#### **3. Database Models**
- ✅ `clients` - Company/client information
- ✅ `users` - User accounts with roles
- ✅ `documents` - Uploaded document tracking
- ✅ `entries` - Customs entry records
- ✅ `line_items` - Entry line items
- ✅ `skus` - Product/SKU tracking
- ✅ `classification_alternatives` - HTS alternatives (schema ready)
- ✅ `psc_opportunities` - PSC opportunities (schema ready)

#### **4. Document Processing Engine**
- ✅ PDF text extraction (pdfplumber)
- ✅ Excel/CSV parsing (pandas)
- ✅ Document type detection (Commercial Invoice, Entry Summary, etc.)
- ✅ Claude AI integration for intelligent field extraction
- ✅ Commercial Invoice processor
- ✅ Entry Summary (7501) processor

#### **5. API Endpoints**
- ✅ `POST /api/v1/auth/register` - Register client
- ✅ `POST /api/v1/auth/login` - User login
- ✅ `GET /api/v1/auth/me` - Get current user
- ✅ `POST /api/v1/documents/upload` - Upload document
- ✅ `GET /api/v1/documents` - List documents
- ✅ `GET /api/v1/documents/{id}` - Get document details
- ✅ `GET /health` - Health check

#### **6. Data Extraction Capabilities**
- ✅ Extract from Commercial Invoices:
  - PO numbers, invoice numbers, dates
  - Supplier/buyer information
  - Line items (description, quantity, price, HTS codes)
  - Total values, currency, incoterms
  - Country of origin

- ✅ Extract from Entry Summaries:
  - Entry numbers (11-digit)
  - Entry type, date, port of entry
  - Importer number, filer
  - Line items with HTS codes
  - Duty rates and amounts
  - Section 301 tariffs

### **Time:** 2.5 hours
### **Status:** ✅ Complete

---

## ✅ **SPRINT 2: Intelligent Extraction (COMPLETE)**

### **Objective:**
Enhance document processing to handle scanned documents, complex layouts, and enable batch processing of all AURA shipments.

### **What Was Built:**

#### **1. OCR Integration**
- ✅ Tesseract OCR integration
- ✅ Automatic fallback from text extraction to OCR
- ✅ Handles scanned/non-machine-readable PDFs
- ✅ Image preprocessing for better accuracy
- ✅ Detection of extraction method (text vs OCR)

#### **2. Claude Vision API**
- ✅ Vision API integration for image-based processing
- ✅ Automatic detection when to use Vision API
- ✅ Process complex table layouts
- ✅ Handle low-quality scans
- ✅ Extract from images directly
- ✅ Higher confidence scores (90%+)

#### **3. Enhanced Entry Summary Parser**
- ✅ Multi-page form support
- ✅ Better Section 301 detection
- ✅ ACE/CBP format variations
- ✅ Improved field extraction accuracy

#### **4. Document Linking System**
- ✅ CI + ES auto-linking by PO number
- ✅ Multi-strategy line item matching:
  - Line number matching
  - Description similarity (fuzzy matching)
  - HTS code matching
- ✅ Value discrepancy detection
- ✅ Confidence scoring (high/medium/low)
- ✅ Automatic flagging of mismatches
- ✅ Detailed discrepancy reporting

#### **5. Batch Processing**
- ✅ `POST /api/v1/documents/upload/batch` endpoint
- ✅ Upload multiple documents at once
- ✅ Individual success/failure tracking
- ✅ Process all 25 AURA shipments efficiently

#### **6. Frontend Interface**
- ✅ Simple web interface (HTML/JS)
- ✅ User registration form with validation
- ✅ Drag & drop file upload
- ✅ Real-time processing results
- ✅ Form validation (EIN auto-formatting, email validation)
- ✅ Accessible at http://localhost:9001

#### **7. New API Endpoints**
- ✅ `POST /api/v1/documents/upload/batch` - Batch upload
- ✅ `POST /api/v1/documents/link` - Link CI and ES documents

### **Time:** 2.5 hours
### **Status:** ✅ Complete

---

## ⏳ **SPRINT 3: Classification Engine (NEXT UP - HIGH PRIORITY)**

### **Objective:**
Build the core money-making feature: generate alternative HTS codes, calculate duty savings, and identify classification opportunities.

### **What Will Be Built:**

#### **1. Alternative HTS Code Generator**
- ⏳ Analyze product descriptions using Claude AI
- ⏳ Generate 3-5 alternative HTS codes per product
- ⏳ Understand product characteristics:
  - Material composition
  - Function/purpose
  - Physical attributes
  - Industry classification
- ⏳ Consider context (country of origin, use case)
- ⏳ API endpoint: `POST /api/v1/classification/analyze`

#### **2. GRI (General Rules of Interpretation) Analysis**
- ⏳ Apply GRI rules to determine most appropriate classification
- ⏳ GRI 1: Legal text and notes
- ⏳ GRI 2: Incomplete/unfinished goods
- ⏳ GRI 3: Multiple possible classifications
- ⏳ GRI 4: Most similar goods
- ⏳ GRI 5: Containers/cases
- ⏳ GRI 6: Subheadings
- ⏳ Document reasoning for each alternative

#### **3. CROSS Rulings Integration**
- ⏳ Search CBP CROSS (Customs Rulings Online Search System) database
- ⏳ Find similar products with precedent classifications
- ⏳ Extract relevant rulings:
  - Ruling number
  - Product description
  - HTS classification
  - Reasoning
- ⏳ Match products to similar rulings
- ⏳ Use rulings as justification for alternatives

#### **4. Duty Rate Calculator**
- ⏳ Fetch current duty rates for each HTS code:
  - Column 1 rates (NTR/MFN - Normal Trade Relations)
  - Column 2 rates (if applicable)
  - Special rates (FTA, GSP, etc.)
- ⏳ Calculate Section 301 tariffs
- ⏳ Calculate total landed cost:
  - Base value
  - Duty amount
  - Section 301 amount
  - Total cost
- ⏳ Compare current vs. alternative costs

#### **5. Risk Scoring System**
- ⏳ Classification confidence score (0-100)
  - Based on description match quality
  - Based on CROSS ruling matches
  - Based on GRI analysis
- ⏳ Regulatory compliance risk:
  - Audit likelihood
  - CBP scrutiny level
  - Historical enforcement
- ⏳ Documentation quality:
  - Ruling references available
  - Precedent cases found
  - Justification strength

#### **6. Recommendation Engine**
- ⏳ Generate recommendations:
  - "You're paying $X, could pay $Y"
  - Potential savings calculation
  - Risk assessment
  - Action items
- ⏳ Prioritize recommendations:
  - Highest savings first
  - Lowest risk first
  - Best risk/reward ratio
- ⏳ Generate justification documentation:
  - HTS code reasoning
  - CROSS ruling references
  - GRI analysis
  - Supporting evidence

#### **7. API Endpoints to Build**
- ⏳ `POST /api/v1/classification/analyze` - Analyze product and generate alternatives
- ⏳ `GET /api/v1/classification/alternatives/{sku_id}` - Get alternatives for SKU
- ⏳ `POST /api/v1/classification/compare` - Compare multiple HTS codes
- ⏳ `GET /api/v1/classification/cross-rulings` - Search CROSS rulings
- ⏳ `GET /api/v1/classification/duty-rates/{hts_code}` - Get duty rates

#### **8. Database Updates**
- ⏳ Populate `classification_alternatives` table
- ⏳ Store CROSS ruling references
- ⏳ Store GRI analysis results
- ⏳ Store risk scores
- ⏳ Store savings calculations

### **Technical Requirements:**
- CROSS Rulings API or web scraping
- HTSUS duty rate database (USITC or CBP)
- Enhanced Claude prompts for classification
- Vector search for similar products (optional)

### **Deliverables:**
- Alternative HTS codes for every SKU
- Duty savings opportunities identified
- Risk assessment for each classification
- CBP ruling references
- Justification documentation

### **Success Criteria:**
- Generate 3-5 viable alternatives per product
- Identify at least 10% duty savings opportunities
- Risk scores accurate and actionable
- CROSS rulings found for 70%+ of products

### **Time Estimate:** 3 hours
### **Priority:** **HIGH** 💰 (Core money-making feature)

---

## 📋 **SPRINT 4: PSC Radar (HIGH PRIORITY)**

### **Objective:**
Automatically scan all entries for Post Summary Correction opportunities and track liquidation deadlines to maximize refund potential.

### **What Will Be Built:**

#### **1. Entry Scanner**
- ⏳ Analyze all past entries for misclassifications
- ⏳ Compare entered HTS codes vs. recommended alternatives
- ⏳ Identify entries with potential savings:
  - Higher duty rate used
  - Better classification available
  - CROSS ruling support
- ⏳ Calculate potential refund amounts
- ⏳ Flag entries within liquidation window

#### **2. Liquidation Countdown System**
- ⏳ Track 314-day deadline from entry date
- ⏳ Calculate days remaining for each entry
- ⏳ Priority scoring: `$savings × days_remaining`
- ⏳ Automated alerts:
  - 60 days remaining
  - 30 days remaining
  - 14 days remaining
  - 7 days remaining
- ⏳ Urgency indicators

#### **3. Opportunity Dashboard**
- ⏳ List all PSC opportunities
- ⏳ Sort by:
  - Potential savings (highest first)
  - Days remaining (most urgent first)
  - Priority score (best ROI first)
- ⏳ Filter by:
  - Risk level
  - Entry date range
  - Savings threshold
  - Status (new, in-progress, submitted)
- ⏳ Quick-action buttons:
  - Generate PSC
  - View details
  - Mark as submitted

#### **4. PSC Form Generator**
- ⏳ Auto-fill CBP Form 7501 (PSC)
- ⏳ Generate justification documentation:
  - Current vs. proposed HTS code
  - Reasoning for change
  - CROSS ruling references
  - GRI analysis
  - Supporting evidence
- ⏳ Export submission packages:
  - PDF forms
  - Supporting documents
  - Cover letter
- ⏳ Track submission status

#### **5. Savings Calculator**
- ⏳ Calculate potential refunds:
  - Duty overpayment
  - Section 301 overpayment
  - Total refund amount
- ⏳ Portfolio-level analysis:
  - Total potential savings
  - By entry
  - By product category
  - By time period
- ⏳ ROI calculation:
  - Cost to file PSC
  - Expected refund
  - Net benefit

#### **6. API Endpoints to Build**
- ⏳ `POST /api/v1/psc/scan` - Scan entries for opportunities
- ⏳ `GET /api/v1/psc/opportunities` - List all opportunities
- ⏳ `GET /api/v1/psc/opportunities/{id}` - Get opportunity details
- ⏳ `POST /api/v1/psc/generate/{entry_id}` - Generate PSC form
- ⏳ `GET /api/v1/psc/dashboard` - Dashboard summary
- ⏳ `POST /api/v1/psc/submit/{id}` - Mark as submitted

#### **7. Database Updates**
- ⏳ Populate `psc_opportunities` table
- ⏳ Store liquidation deadlines
- ⏳ Track submission status
- ⏳ Store generated forms

### **Technical Requirements:**
- Integration with classification engine
- PDF form generation library
- Date calculation utilities
- Priority scoring algorithm

### **Deliverables:**
- Complete scan of all 25 AURA entries
- Ranked list of PSC opportunities
- Potential refund amounts
- Ready-to-submit PSC packages
- Liquidation deadline tracking

### **Success Criteria:**
- Identify opportunities in 100% of entries
- Calculate accurate refund amounts
- Generate submission-ready forms
- Track all deadlines accurately

### **Time Estimate:** 2.5 hours
### **Priority:** **HIGH** 💰 (Automatic money-finder)

---

## 📋 **SPRINT 5: Frontend Dashboard (MEDIUM PRIORITY)**

### **Objective:**
Build a modern, user-friendly frontend interface for managing documents, classifications, and PSC opportunities.

### **What Will Be Built:**

#### **1. React/Next.js Frontend**
- ⏳ Modern React application
- ⏳ Next.js framework for SSR/SSG
- ⏳ TypeScript for type safety
- ⏳ Tailwind CSS for styling
- ⏳ Responsive design (mobile-friendly)

#### **2. Document Management Views**
- ⏳ Document list with search/filter
- ⏳ Document detail view
- ⏳ PDF viewer (inline)
- ⏳ Extracted data display
- ⏳ Document linking interface
- ⏳ Batch upload interface

#### **3. Entry Management**
- ⏳ Entry list with search/filter
- ⏳ Entry detail view
- ⏳ Line items display
- ⏳ Linked documents view
- ⏳ Entry comparison tool

#### **4. Classification Workbench**
- ⏳ Product classification interface
- ⏳ Side-by-side comparison:
  - Current HTS code
  - Alternative HTS codes
  - Duty rates
  - Savings potential
- ⏳ Accept/reject alternatives
- ⏳ Notes and justifications
- ⏳ CROSS ruling viewer
- ⏳ Risk score visualization

#### **5. PSC Dashboard**
- ⏳ Opportunity cards with:
  - Entry information
  - Potential savings
  - Days remaining countdown
  - Risk level indicator
- ⏳ Sortable/filterable list
- ⏳ Priority scoring display
- ⏳ Quick actions (generate, submit)
- ⏳ Calendar view for deadlines

#### **6. Analytics & Reporting**
- ⏳ Savings summary dashboard
- ⏳ Charts and graphs:
  - Savings by entry
  - Savings by product category
  - Timeline of opportunities
  - Risk distribution
- ⏳ Export reports (PDF, Excel)
- ⏳ Custom date ranges

#### **7. User Experience Features**
- ⏳ Real-time updates
- ⏳ Drag & drop file upload
- ⏳ Keyboard shortcuts
- ⏳ Dark mode
- ⏳ Notifications/alerts
- ⏳ Help/tooltips

### **Technical Requirements:**
- React 18+
- Next.js 14+
- TypeScript
- Tailwind CSS
- Chart.js or Recharts
- PDF.js for document viewing

### **Deliverables:**
- Modern, responsive web application
- All core features accessible via UI
- Beautiful, intuitive interface
- Mobile-friendly design

### **Success Criteria:**
- All backend features accessible via UI
- Fast page loads (<2s)
- Intuitive navigation
- Works on mobile devices

### **Time Estimate:** 4 hours
### **Priority:** Medium (Enhances usability)

---

## 📋 **SPRINT 6: Advanced Features (LOW PRIORITY)**

### **Objective:**
Add advanced features for power users, regulatory intelligence, and enterprise capabilities.

### **What Will Be Built:**

#### **1. Bulk Operations**
- ⏳ Folder drag & drop upload
- ⏳ Bulk classification processing
- ⏳ Bulk PSC generation
- ⏳ Export to Excel/CSV
- ⏳ Import from Excel/CSV
- ⏳ Template downloads

#### **2. Regulatory Intelligence**
- ⏳ HTSUS update monitoring
- ⏳ Section 301 change alerts
- ⏳ CBP bulletin scraping
- ⏳ Trade news aggregation
- ⏳ Regulatory change notifications
- ⏳ Impact analysis on existing entries

#### **3. Client Portal**
- ⏳ Multi-user access
- ⏳ Role-based permissions:
  - Admin
  - Analyst
  - Viewer
- ⏳ Activity audit log
- ⏳ User management
- ⏳ Team collaboration features

#### **4. Reporting & Analytics**
- ⏳ Duty analysis reports
- ⏳ Compliance scorecards
- ⏳ Savings summaries
- ⏳ Custom report builder
- ⏳ Scheduled reports
- ⏳ Email delivery

#### **5. Integration Features**
- ⏳ API documentation
- ⏳ Webhook support
- ⏳ Third-party integrations:
  - ERP systems
  - Customs brokers
  - Trade management software
- ⏳ Data export formats

#### **6. Advanced Classification**
- ⏳ Machine learning model training
- ⏳ Historical classification learning
- ⏳ Custom classification rules
- ⏳ Product categorization
- ⏳ Similarity matching

### **Technical Requirements:**
- Webhook infrastructure
- Scheduled task system (Celery)
- Email service integration
- API rate limiting
- Advanced analytics libraries

### **Deliverables:**
- Enterprise-ready features
- Regulatory monitoring system
- Advanced reporting
- Integration capabilities

### **Success Criteria:**
- All advanced features working
- Regulatory alerts accurate
- Reports generated correctly
- Integrations functional

### **Time Estimate:** 3 hours
### **Priority:** Low (Nice-to-have features)

---

## 🎯 **SPRINT DEPENDENCIES**

```
Sprint 1 (Foundation)
  └─> Sprint 2 (Intelligent Extraction)
        └─> Sprint 3 (Classification Engine)
              └─> Sprint 4 (PSC Radar)
                    └─> Sprint 5 (Frontend Dashboard)
                          └─> Sprint 6 (Advanced Features)
```

**Critical Path:**
- Sprint 3 depends on Sprint 1 & 2 (document processing)
- Sprint 4 depends on Sprint 3 (classification engine)
- Sprint 5 can be built in parallel with Sprint 4
- Sprint 6 depends on all previous sprints

---

## 📊 **SUCCESS METRICS BY SPRINT**

### **Sprint 1 & 2 (Complete):**
- ✅ 11 API endpoints working
- ✅ Document processing: 90%+ confidence
- ✅ OCR + Vision API integrated
- ✅ Batch processing capability
- ✅ Smart document linking

### **Sprint 3 (Target):**
- Generate 3-5 alternatives per product
- Identify 10%+ duty savings opportunities
- 70%+ products with CROSS ruling matches
- Risk scores accurate and actionable

### **Sprint 4 (Target):**
- Scan 100% of entries for opportunities
- Calculate accurate refund amounts
- Generate submission-ready forms
- Track all deadlines accurately

### **Sprint 5 (Target):**
- All features accessible via UI
- Page loads <2s
- Mobile-friendly
- Intuitive navigation

### **Sprint 6 (Target):**
- Regulatory alerts accurate
- Reports generated correctly
- Integrations functional

---

## 🚀 **RECOMMENDED EXECUTION ORDER**

### **Phase 1: Core Value (Sprints 1-4) - 10.5 hours**
**Focus:** Build the money-making features
1. ✅ Sprint 1: Foundation (DONE)
2. ✅ Sprint 2: Intelligent Extraction (DONE)
3. ⏳ Sprint 3: Classification Engine (NEXT)
4. ⏳ Sprint 4: PSC Radar

**Outcome:** Fully functional platform that finds and generates duty savings

### **Phase 2: User Experience (Sprint 5) - 4 hours**
**Focus:** Make it beautiful and easy to use
5. ⏳ Sprint 5: Frontend Dashboard

**Outcome:** Modern, user-friendly interface

### **Phase 3: Enterprise Features (Sprint 6) - 3 hours**
**Focus:** Advanced features for power users
6. ⏳ Sprint 6: Advanced Features

**Outcome:** Enterprise-ready platform

---

## 💰 **BUSINESS VALUE BY SPRINT**

| Sprint | Business Value | ROI |
|--------|---------------|-----|
| Sprint 1 | Foundation | Infrastructure |
| Sprint 2 | Better extraction | Quality |
| **Sprint 3** | **Find savings** | **💰💰💰 HIGH** |
| **Sprint 4** | **Generate refunds** | **💰💰💰 HIGH** |
| Sprint 5 | Better UX | Adoption |
| Sprint 6 | Enterprise features | Scale |

**Key Insight:** Sprints 3 & 4 are the money-makers. Everything else supports them.

---

## 🎯 **CURRENT PRIORITIES**

### **Immediate (Next Session):**
1. **Sprint 3: Classification Engine** (3 hours)
   - This is THE core feature
   - Generates alternative HTS codes
   - Calculates duty savings
   - Finds opportunities

### **Short-term (After Sprint 3):**
2. **Sprint 4: PSC Radar** (2.5 hours)
   - Automatically finds refund opportunities
   - Tracks deadlines
   - Generates submission forms

### **Medium-term:**
3. **Sprint 5: Frontend Dashboard** (4 hours)
   - Better user experience
   - Modern interface

### **Long-term:**
4. **Sprint 6: Advanced Features** (3 hours)
   - Enterprise capabilities
   - Regulatory intelligence

---

## 📝 **NOTES & CONSIDERATIONS**

### **Technical Decisions Needed:**
1. **CROSS Rulings:**
   - API access or web scraping?
   - How to search efficiently?
   - Update frequency?

2. **Duty Rate Data:**
   - Source: USITC, CBP, or third-party?
   - Update frequency?
   - Column 1 vs Column 2?

3. **HTS Code Alternatives:**
   - How many to generate? (3-5 recommended)
   - Confidence threshold?
   - How to handle ambiguous products?

4. **PSC Priority:**
   - Minimum savings threshold?
   - How to calculate priority score?
   - Deadline handling?

### **Risks & Mitigations:**
- **Risk:** CROSS rulings API unavailable
  - **Mitigation:** Web scraping fallback
- **Risk:** Duty rate data outdated
  - **Mitigation:** Regular updates, caching
- **Risk:** Classification accuracy
  - **Mitigation:** Human review, confidence scores

---

## 🎉 **COMPLETION CRITERIA**

**Project is "complete" when:**
- ✅ All 6 sprints finished
- ✅ 25 AURA shipments processed
- ✅ Classification alternatives generated
- ✅ PSC opportunities identified
- ✅ Frontend dashboard functional
- ✅ Ready for production use

**Total Time to Complete:** ~18 hours  
**Current Progress:** 28% (5 hours done, 13 hours remaining)

---

**This document provides the complete roadmap for building NECO from current state to full platform.**


