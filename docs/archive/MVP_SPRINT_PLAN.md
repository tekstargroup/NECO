# MVP Sprint Plan - NECO

## Current State Assessment

### ✅ What's Complete (Sprints 5-11)
- **Backend API**: Fully functional with all core features
- **HTS Extraction & Duty Resolution**: Production-ready
- **PSC Radar**: Read-only intelligence
- **Review/Audit System**: Complete with RBAC
- **Broker Export**: Filing-prep with validation
- **Document Enrichment**: Evidence-backed extraction
- **UX Design**: Complete documentation and language guide

### ❌ What's Missing for MVP
- **Frontend**: No UI implementation (only design docs)
- **End-to-End Workflow**: APIs exist but not connected in a flow
- **User Onboarding**: No registration/login UI
- **Deployment**: Development-only setup
- **Error Handling**: Backend has it, frontend doesn't exist

---

## MVP Definition

**Minimum Viable Product = Core "Happy Path" Working End-to-End**

A compliance director can:
1. **Log in** to NECO
2. **Upload a Commercial Invoice** (or enter shipment details manually)
3. **See analysis results** (HTS code, duty rates, PSC flags, money impact)
4. **Review and accept/reject** the classification
5. **Export filing-prep bundle** for broker handoff

**Time to value: < 5 minutes from login to export**

---

## Recommended Sprint Sequence

### **SPRINT 12: Frontend Foundation** (Priority: CRITICAL)
**Goal:** Build the frontend infrastructure and core UI components

**Why First:** Everything else depends on having a UI

**Deliverables:**
- [ ] Choose frontend framework (Recommendation: **React + TypeScript** for compliance-grade feel)
- [ ] Set up build pipeline (Vite/Next.js)
- [ ] Implement authentication UI (login, register, protected routes)
- [ ] Create layout components (header, navigation, container)
- [ ] Set up API client with error handling
- [ ] Implement loading states and error boundaries
- [ ] Basic routing structure

**Tech Stack Recommendation:**
- **React 18+** with TypeScript
- **Vite** (fast, simple) or **Next.js 14** (if SSR needed)
- **Tailwind CSS** (utility-first, conservative styling)
- **React Query/TanStack Query** (API state management)
- **React Hook Form** (form handling)
- **Zod** (client-side validation matching Pydantic)

**Success Criteria:**
- User can log in and see authenticated state
- API calls work with proper error handling
- Layout matches Sprint 11 UX design principles

**Estimated Time:** 1-2 weeks

---

### **SPRINT 13: Core Workflow - Shipment Analysis** (Priority: CRITICAL)
**Goal:** Implement the primary "Analyze a shipment" workflow

**Why Second:** This is the core value proposition

**Deliverables:**
- [ ] **Entry Screen**: "Analyze a shipment" landing page
  - Document upload (drag & drop)
  - Manual entry form (product description, HTS, quantity, value)
  - Historical entry reference (optional)
- [ ] **Shipment Analysis View** (8 sections from Sprint 11):
  1. Outcome Summary
  2. Money Impact
  3. Risk Summary
  4. Structural Analysis
  5. PSC Radar
  6. Enrichment Evidence
  7. Review Status
  8. Audit Trail
- [ ] Integration with backend APIs:
  - `/api/v1/enrichment/documents/ingest` (upload)
  - `/api/v1/enrichment/documents/{id}/extract` (extract fields)
  - `/api/v1/classification/generate` (classify)
  - `/api/v1/broker/filing-prep` (get bundle)
- [ ] Loading states during processing
- [ ] Error handling for failed extractions/classifications

**Success Criteria:**
- User can upload CI → see extracted fields → see classification → see analysis
- All 8 sections render correctly with real data
- Money impact is prominent but calm (per Sprint 11)
- Conflicts are visually uncomfortable (not hidden)

**Estimated Time:** 2-3 weeks

---

### **SPRINT 14: Review & Override Workflow** (Priority: HIGH)
**Goal:** Implement review and override functionality

**Why Third:** Required for compliance director workflow

**Deliverables:**
- [ ] Review status display (DRAFT, REVIEW_REQUIRED, REVIEWED_ACCEPTED, etc.)
- [ ] Submit for review button/flow
- [ ] Review action UI (accept/reject with notes)
- [ ] Override UI (serious, frictionful, with audit warning)
- [ ] Review history timeline
- [ ] RBAC enforcement (only REVIEWER can finalize)
- [ ] Integration with `/api/v1/compliance/drilldown/{review_id}`

**Success Criteria:**
- Analyst can submit for review
- Reviewer can accept/reject with notes
- Override requires justification and shows audit warning
- Review history is visible and auditable

**Estimated Time:** 1-2 weeks

---

### **SPRINT 15: Broker Export & Handoff** (Priority: HIGH)
**Goal:** Implement broker export functionality

**Why Fourth:** Completes the end-to-end workflow

**Deliverables:**
- [ ] Export button/actions (JSON, CSV, PDF)
- [ ] Export validation (block if REVIEW_REQUIRED, show clear errors)
- [ ] Broker handoff view (conservative, printable format)
- [ ] PDF generation (client-side or server-side)
- [ ] Download functionality
- [ ] Integration with `/api/v1/broker/filing-prep/export`

**Success Criteria:**
- User can export filing-prep bundle in all formats
- Export is blocked with clear errors if validation fails
- PDF looks conservative and compliance-grade
- Disclaimers are prominent

**Estimated Time:** 1 week

---

### **SPRINT 16: Polish & Error Handling** (Priority: MEDIUM)
**Goal:** Production-ready error handling and UX polish

**Why Fifth:** Ensures reliability and trust

**Deliverables:**
- [ ] Comprehensive error handling (network, validation, server errors)
- [ ] Loading states for all async operations
- [ ] Empty states (no shipments, no results)
- [ ] Form validation (client-side + server-side)
- [ ] Toast notifications (success, error, warning)
- [ ] Accessibility basics (ARIA labels, keyboard navigation)
- [ ] Mobile responsiveness (at least tablet-friendly)
- [ ] Language pass (remove any remaining AI/tech language)

**Success Criteria:**
- No unhandled errors
- All user actions have feedback
- Forms validate before submission
- Accessible to screen readers

**Estimated Time:** 1-2 weeks

---

### **SPRINT 17: Deployment & Infrastructure** (Priority: MEDIUM)
**Goal:** Deploy MVP to production-ready environment

**Why Sixth:** Needed for real users

**Deliverables:**
- [ ] Production build configuration
- [ ] Environment variable management
- [ ] Docker containerization (if not already)
- [ ] CI/CD pipeline (GitHub Actions/GitLab CI)
- [ ] Deployment to cloud (AWS/GCP/Azure)
- [ ] Database migrations in production
- [ ] Monitoring and logging (Sentry, DataDog, etc.)
- [ ] Health checks and uptime monitoring

**Success Criteria:**
- MVP deployed and accessible
- CI/CD runs tests and deploys automatically
- Monitoring shows system health
- Database migrations run safely

**Estimated Time:** 1-2 weeks

---

## Alternative: Faster MVP Path

If you need to validate faster, consider this condensed approach:

### **SPRINT 12A: Minimal Frontend (1 week)**
- React + TypeScript setup
- Authentication UI only
- Single page: Shipment Analysis View
- Hard-code one example shipment
- Manual API calls (no workflow)

**Goal:** Show working UI with real backend data

### **SPRINT 13A: Core Workflow Only (1 week)**
- Document upload → Classification → Results
- Skip review/override for now
- Skip broker export for now
- Focus on: Upload → See Results

**Goal:** End-to-end happy path working

### **SPRINT 14A: Essential Polish (3-4 days)**
- Error handling
- Loading states
- Basic validation

**Goal:** Demo-ready MVP

**Total Time:** ~2.5 weeks for demo-ready MVP

---

## Recommended Tech Stack Summary

### Frontend
- **React 18+** with TypeScript
- **Vite** (build tool)
- **Tailwind CSS** (styling)
- **TanStack Query** (API state)
- **React Hook Form + Zod** (forms/validation)
- **React Router** (routing)

### Why This Stack?
- **React**: Industry standard, large talent pool, compliance-grade feel
- **TypeScript**: Type safety matches backend Pydantic models
- **Tailwind**: Fast development, conservative styling matches Sprint 11
- **TanStack Query**: Handles caching, loading, errors automatically
- **Vite**: Fast dev server, simple production builds

### Alternative: Next.js
If you want SSR/SSG:
- **Next.js 14** (App Router)
- Same libraries otherwise
- Better SEO (not needed for MVP)
- More complex setup

---

## Critical Success Factors

1. **Follow Sprint 11 UX Design Exactly**
   - Conservative language
   - Money-first but calm
   - No AI vibes
   - Infrastructure-grade feel

2. **API Integration First**
   - Don't build UI without backend integration
   - Test with real API responses
   - Handle all error cases

3. **Mobile-First (or at least Responsive)**
   - Compliance directors use tablets
   - Must work on iPad/tablet
   - Desktop is primary but not only

4. **Accessibility from Day 1**
   - Screen reader support
   - Keyboard navigation
   - ARIA labels
   - Color contrast

5. **Error Handling is Trust**
   - Clear error messages
   - No technical jargon
   - Actionable guidance
   - Never show stack traces

---

## MVP Validation Criteria

Sprint plan is complete when:

- [ ] Compliance director can log in
- [ ] Upload CI → See analysis → Export bundle in < 5 minutes
- [ ] All 8 sections of analysis view work
- [ ] Review/override workflow functional
- [ ] Export blocked with clear errors if invalid
- [ ] No unhandled errors
- [ ] Language matches Sprint 11 guide
- [ ] Feels conservative, not clever
- [ ] Money impact obvious but not pushy

---

## Next Steps

1. **Decide on frontend framework** (Recommend: React + TypeScript)
2. **Set up frontend project** (Vite or Next.js)
3. **Start Sprint 12** (Frontend Foundation)
4. **Iterate based on user feedback** after each sprint

**Estimated Total Time to MVP:** 6-10 weeks (or 2.5 weeks for minimal demo)

---

## Questions to Answer Before Starting

1. **Who will build the frontend?** (You, team, contractor?)
2. **What's the target deployment?** (Cloud, on-prem, hybrid?)
3. **Who are the first 3-5 users?** (Get them involved early)
4. **What's the MVP deadline?** (Drives sprint prioritization)
5. **Do you need mobile app?** (Or web-responsive is enough?)

---

**Recommendation:** Start with Sprint 12 (Frontend Foundation) immediately. Everything else depends on having a working UI.
