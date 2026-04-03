/**
 * Documents Tab - Sprint 12
 * 
 * Document list + upload with S3 presigned flow.
 */

"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { Upload, FileText, FileSpreadsheet, Trash2, X } from "lucide-react"
import countries from "i18n-iso-countries"
import enCountries from "i18n-iso-countries/langs/en.json"

interface DocumentsTabProps {
  shipment: any
  shipmentId: string
  onRunPreComplianceAnalysis?: () => void
}

type DocumentType = "ENTRY_SUMMARY" | "COMMERCIAL_INVOICE" | "PACKING_LIST" | "DATA_SHEET"

interface ShipmentDocument {
  id: string
  document_type: string
  filename: string
  uploaded_at: string
  retention_expires_at: string
  processing_status?: string | null
  extraction_method?: string | null
  ocr_used?: boolean | null
  page_count?: number | null
  char_count?: number | null
  table_detected?: boolean | null
  extraction_status?: string | null
  usable_for_analysis?: boolean | null
  data_sheet_user_confirmed?: boolean
}

function isDataSheetEvidenceReady(doc: ShipmentDocument | undefined): boolean {
  if (!doc || doc.document_type !== "DATA_SHEET") return false
  if (doc.data_sheet_user_confirmed) return true
  return doc.usable_for_analysis === true && (doc.char_count ?? 0) > 0
}

countries.registerLocale(enCountries)
const COUNTRY_NAME_MAP = countries.getNames("en", { select: "official" }) as Record<string, string>
const COUNTRY_OPTIONS = Object.entries(COUNTRY_NAME_MAP)
  .map(([alpha2, name]) => ({
    alpha2,
    alpha3: countries.alpha2ToAlpha3(alpha2) || "",
    name,
  }))
  .sort((a, b) => a.name.localeCompare(b.name))

function normalizeCountryInput(raw: string): string | null {
  const input = String(raw || "").trim()
  if (!input) return null
  const upper = input.toUpperCase()
  if (upper.length === 2 && countries.isValid(upper)) return upper
  if (upper.length === 3) {
    const a2 = countries.alpha3ToAlpha2(upper)
    if (a2 && countries.isValid(a2)) return a2
  }
  const parenCodes = upper.match(/\(([A-Z\/]{2,9})\)/)?.[1]
  if (parenCodes) {
    const firstCode = parenCodes.split("/")[0]?.trim()
    if (firstCode) {
      const normalized = normalizeCountryInput(firstCode)
      if (normalized) return normalized
    }
  }
  const byName = countries.getAlpha2Code(input, "en")
  if (byName && countries.isValid(byName.toUpperCase())) return byName.toUpperCase()
  return null
}

function normalizeLabel(raw: string): string {
  return String(raw || "")
    .toLowerCase()
    .replace(/\.[^.]+$/, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
}

const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
  { value: "ENTRY_SUMMARY", label: "Entry Summary" },
  { value: "COMMERCIAL_INVOICE", label: "Commercial Invoice" },
  { value: "PACKING_LIST", label: "Packing List" },
  { value: "DATA_SHEET", label: "Data Sheet" },
]

function documentTypeLabel(value: string): string {
  return DOCUMENT_TYPES.find((t) => t.value === value)?.label ?? value.replace(/_/g, " ")
}

const ALLOWED_FILE_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "text/csv",
]
const ALLOWED_EXT_REGEX = /\.(pdf|docx|xlsx|xls|csv)$/i

function getContentType(file: File): string {
  if (file.type && ALLOWED_FILE_TYPES.includes(file.type)) return file.type
  const ext = file.name.toLowerCase().split(".").pop()
  const map: Record<string, string> = {
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    xls: "application/vnd.ms-excel",
    csv: "text/csv",
  }
  return map[ext || ""] || "application/octet-stream"
}

function isAllowedFile(file: File): boolean {
  return ALLOWED_FILE_TYPES.includes(file.type) || ALLOWED_EXT_REGEX.test(file.name)
}

/** Infer document type from filename for better defaults (e.g. "ES 579008.pdf" -> Entry Summary). */
function defaultDocTypeFromFilename(filename: string): DocumentType {
  const lower = filename.toLowerCase()
  if (/\bes\b|entry[- ]?summary|entrysummary/i.test(lower)) return "ENTRY_SUMMARY"
  if (/\bci\b|commercial[- ]?invoice|invoice/i.test(lower)) return "COMMERCIAL_INVOICE"
  if (/packing|pack[- ]?list/i.test(lower)) return "PACKING_LIST"
  if (/data[- ]?sheet|datasheet/i.test(lower)) return "DATA_SHEET"
  return "COMMERCIAL_INVOICE"
}

function DocumentIcon({ filename }: { filename: string }) {
  const ext = filename.toLowerCase().split(".").pop()
  if (ext === "pdf") return <FileText className="h-5 w-5 shrink-0 text-red-600" aria-hidden />
  if (["xlsx", "xls", "csv"].includes(ext || "")) return <FileSpreadsheet className="h-5 w-5 shrink-0 text-green-700" aria-hidden />
  return <FileText className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
}

interface PendingFile {
  id: string
  file: File
  docType: DocumentType
}

export function DocumentsTab({ shipment, shipmentId, onRunPreComplianceAnalysis }: DocumentsTabProps) {
  const { apiGet, apiPost, apiPatch, apiPut, apiDelete } = useApiClient()
  const shipmentTypeRef = (shipment?.references || []).find((r: any) => String(r?.key || "").toUpperCase() === "SHIPMENT_TYPE")
  const shipmentType = String(shipmentTypeRef?.value || "PRE_COMPLIANCE").toUpperCase()
  const isPreCompliance = shipmentType !== "ENTRY_COMPLIANCE"
  const [documents, setDocuments] = useState<ShipmentDocument[]>([])
  const [analysisItems, setAnalysisItems] = useState<any[]>([])
  const [shipmentItems, setShipmentItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [supplementalUrl, setSupplementalUrl] = useState<Record<string, string>>({})
  const [countryOfOriginInput, setCountryOfOriginInput] = useState<Record<string, string>>({})
  const [supplementalSubmitting, setSupplementalSubmitting] = useState<Record<string, boolean>>({})
  const [error, setError] = useState<string | null>(null)
  const [loadWarnings, setLoadWarnings] = useState<string[]>([])
  const [clarificationError, setClarificationError] = useState<string | null>(null)
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const [reprocessingId, setReprocessingId] = useState<string | null>(null)
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({})
  const [countryPickerOpenFor, setCountryPickerOpenFor] = useState<string | null>(null)
  const [countryPickerHighlightIndex, setCountryPickerHighlightIndex] = useState<Record<string, number>>({})
  const countryInputRefs = useRef<Record<string, HTMLInputElement | null>>({})
  const [trustWorkflow, setTrustWorkflow] = useState<{
    items?: Array<{ item_id?: string; assigned_document_ids?: string[] }>
  } | null>(null)
  const [linkItemChoice, setLinkItemChoice] = useState<Record<string, string>>({})
  const [linkingDocId, setLinkingDocId] = useState<string | null>(null)

  const loadTrustWorkflow = async () => {
    try {
      const tw = await apiGet<{
        items?: Array<{ item_id?: string; assigned_document_ids?: string[] }>
      }>(`/api/v1/shipments/${shipmentId}/trust-workflow`)
      setTrustWorkflow(tw)
      setLoadWarnings((prev) => prev.filter((w) => w !== "workflow"))
    } catch {
      setTrustWorkflow(null)
      setLoadWarnings((prev) => (prev.includes("workflow") ? prev : [...prev, "workflow"]))
    }
  }

  const loadDocuments = async () => {
    try {
      const docs = await apiGet<ShipmentDocument[]>(
        `/api/v1/shipment-documents/shipments/${shipmentId}/documents`
      )
      setDocuments(docs)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setLoading(false)
    }
  }

  const loadAnalysisItems = async () => {
    try {
      const status = await apiGet<any>(`/api/v1/shipments/${shipmentId}/analysis-status`)
      const nextItems = status?.result_json?.items || []
      setAnalysisItems(nextItems)
      const cooByItem: Record<string, string> = {}
      nextItems.forEach((item: any) => {
        if (item?.id) cooByItem[String(item.id)] = String(item.country_of_origin || "")
      })
      setCountryOfOriginInput((prev) => ({ ...cooByItem, ...prev }))
      setLoadWarnings((prev) => prev.filter((w) => w !== "analysis"))
    } catch (e: unknown) {
      const err = e as ApiClientError
      const detail = typeof err.data?.detail === "string" ? err.data.detail : ""
      // Backend returns 404 until the first analysis run exists — expected, not an error state for this tab.
      if (err.status === 404 && detail.toLowerCase().includes("analysis not found")) {
        setAnalysisItems([])
        setLoadWarnings((prev) => prev.filter((w) => w !== "analysis"))
        return
      }
      setAnalysisItems([])
      setLoadWarnings((prev) => (prev.includes("analysis") ? prev : [...prev, "analysis"]))
    }
  }

  const loadShipmentItems = async () => {
    try {
      const detail = await apiGet<any>(`/api/v1/shipments/${shipmentId}`)
      setShipmentItems(detail?.items || [])
      setLoadWarnings((prev) => prev.filter((w) => w !== "items"))
    } catch {
      setShipmentItems([])
      setLoadWarnings((prev) => (prev.includes("items") ? prev : [...prev, "items"]))
    }
  }

  useEffect(() => {
    loadDocuments()
    loadAnalysisItems()
    loadShipmentItems()
    loadTrustWorkflow()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipmentId])

  const addFiles = (files: FileList | File[]) => {
    const arr = Array.from(files)
    const allowed = arr.filter(isAllowedFile)
    const rejected = arr.filter((f) => !isAllowedFile(f))
    if (rejected.length > 0) {
      setError(
        `Skipped ${rejected.length} file(s): only PDF, Word (.docx), and Excel (.xlsx, .xls, .csv) are supported`
      )
    }
    if (rejected.length === 0) setError(null)
    const newPending: PendingFile[] = allowed.map((file) => ({
      id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      docType: defaultDocTypeFromFilename(file.name),
    }))
    setPendingFiles((prev) => [...prev, ...newPending])
  }

  const removePending = (id: string) => {
    setPendingFiles((prev) => prev.filter((p) => p.id !== id))
  }

  const setPendingDocType = (id: string, docType: DocumentType) => {
    setPendingFiles((prev) =>
      prev.map((p) => (p.id === id ? { ...p, docType } : p))
    )
  }

  const uploadOne = async (pf: PendingFile) => {
    const { file, docType } = pf
    const contentType = getContentType(file)

    const presignResponse = await apiPost<{
      upload_url: string
      s3_key: string
      expires_in: number
    }>("/api/v1/shipment-documents/presign", {
      shipment_id: shipmentId,
      document_type: docType,
      filename: file.name,
      content_type: contentType,
    })

    const fileBuffer = await file.arrayBuffer()
    await apiPut(presignResponse.upload_url, fileBuffer, {
      "Content-Type": contentType,
      "X-S3-Key": presignResponse.s3_key,
    })

    const hashBuffer = await crypto.subtle.digest("SHA-256", fileBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const sha256Hash = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("")

    await apiPost("/api/v1/shipment-documents/confirm", {
      shipment_id: shipmentId,
      document_type: docType,
      s3_key: presignResponse.s3_key,
      sha256_hash: sha256Hash,
      filename: file.name,
      content_type: contentType,
      file_size: String(file.size),
    })
  }

  const handleUploadAll = async () => {
    if (pendingFiles.length === 0) return
    const count = pendingFiles.length
    setUploading(true)
    setError(null)
    setClarificationError(null)
    setUploadSuccess(null)
    try {
      for (const pf of pendingFiles) {
        await uploadOne(pf)
      }
      setPendingFiles([])
      await loadDocuments()
      await loadAnalysisItems()
      await loadShipmentItems()
      await loadTrustWorkflow()
      setUploadSuccess(`Uploaded ${count} file${count !== 1 ? "s" : ""}.`)
      setTimeout(() => setUploadSuccess(null), 4000)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setUploading(false)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files?.length) return
    addFiles(files)
    e.target.value = ""
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = e.dataTransfer.files
    if (files?.length) addFiles(files)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false)
  }

  const handleView = async (docId: string) => {
    try {
      const response = await apiGet<{ download_url: string }>(
        `/api/v1/shipment-documents/${docId}/download-url`
      )
      window.open(response.download_url, "_blank")
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    }
  }

  const handleDelete = async (docId: string, filename: string) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this document? Existing analysis will be cleared and you will need to re-run analysis after re-uploading."
    )
    if (!confirmed) return
    setDeletingId(docId)
    setError(null)
    setClarificationError(null)
    try {
      await apiDelete(`/api/v1/shipment-documents/${docId}`)
      await loadDocuments()
      await loadAnalysisItems()
      await loadShipmentItems()
      await loadTrustWorkflow()
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setDeletingId(null)
    }
  }

  const linkedDocIdSet = new Set<string>()
  trustWorkflow?.items?.forEach((it) => {
    ;(it.assigned_document_ids || []).forEach((id) => linkedDocIdSet.add(id))
  })
  const unmatchedDocs = documents.filter((d) => !linkedDocIdSet.has(d.id))

  const dataSheetDocs = documents.filter((d) => d.document_type === "DATA_SHEET")
  const preComplianceRows = isPreCompliance
    ? dataSheetDocs.length > 0
    ? dataSheetDocs.map((doc, idx) => {
        const docLabel = doc.filename.replace(/\.[^.]+$/, "") || `Item ${idx + 1}`
        const docKey = normalizeLabel(docLabel)
        const matchedShipmentItem = shipmentItems.find((it: any) => normalizeLabel(it.label) === docKey)
        const matchedAnalysisItem = analysisItems.find((it: any) => normalizeLabel(it.label) === docKey)
        const matched = matchedAnalysisItem || matchedShipmentItem
        return {
          key: `doc-${doc.id}`,
          itemId: matched?.id ? String(matched.id) : "",
          sourceDocId: doc.id,
          label: docLabel,
          country_of_origin: matched?.country_of_origin || "",
          likelyHts:
            matched?.psc?.alternatives?.[0]?.alternative_hts_code ||
            matched?.classification?.primary_candidate?.hts_code ||
            matched?.hts_code ||
            matched?.declared_hts_code ||
            null,
        }
      })
    : []
    : analysisItems.length > 0
    ? analysisItems.map((item: any, idx: number) => ({
        key: item.id ? String(item.id) : `analysis-${idx}`,
        itemId: item.id ? String(item.id) : "",
        label: item.label || `Item ${idx + 1}`,
        country_of_origin: item.country_of_origin || "",
        likelyHts:
          item?.psc?.alternatives?.[0]?.alternative_hts_code ||
          item?.classification?.primary_candidate?.hts_code ||
          item?.hts_code ||
          null,
      }))
    : shipmentItems.map((item: any, idx: number) => ({
        key: item.id ? String(item.id) : `shipment-${idx}`,
        itemId: item.id ? String(item.id) : "",
        label: item.label || `Item ${idx + 1}`,
        country_of_origin: item.country_of_origin || "",
        likelyHts: item.declared_hts_code || null,
      }))

  useEffect(() => {
    if (!isPreCompliance || preComplianceRows.length === 0) return
    setExpandedItems((prev) => {
      const next: Record<string, boolean> = { ...prev }
      preComplianceRows.forEach((row) => {
        const savedCoo = String(row.country_of_origin || "").toUpperCase()
        const hasSavedCoo = savedCoo.length === 2
        if (next[row.key] == null) next[row.key] = !hasSavedCoo
      })
      return next
    })
  }, [isPreCompliance, preComplianceRows.length, countryOfOriginInput])

  const completedCooCount = preComplianceRows.filter((row) => {
    const savedCoo = String(row.country_of_origin || "").toUpperCase()
    return savedCoo.length === 2
  }).length
  const totalCooCount = preComplianceRows.length
  const allCooComplete = totalCooCount > 0 && completedCooCount === totalCooCount

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Documents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            type="file"
            accept=".pdf,.docx,.xlsx,.xls,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
            onChange={handleFileSelect}
            disabled={uploading}
            multiple
            className="hidden"
            id="file-upload"
          />

          {/* When files are pending, show categorize first (required step) */}
          {pendingFiles.length > 0 && (
            <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50/80 p-4">
              <p className="text-sm font-medium text-amber-900">
                Choose document type for each file, then click Upload.
              </p>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {pendingFiles.map((pf) => (
                  <div
                    key={pf.id}
                    className="flex items-center gap-3 p-3 border border-amber-200 rounded-md bg-white"
                  >
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate flex-1 min-w-0 font-medium">{pf.file.name}</span>
                    <label className="sr-only">Document type for {pf.file.name}</label>
                    <select
                      value={pf.docType}
                      onChange={(e) => setPendingDocType(pf.id, e.target.value as DocumentType)}
                      disabled={uploading}
                      className="px-3 py-2 text-sm border rounded-md bg-background shrink-0 font-medium"
                      aria-label={`Type for ${pf.file.name}`}
                    >
                      {DOCUMENT_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0"
                      onClick={(e) => {
                        e.stopPropagation()
                        removePending(pf.id)
                      }}
                      disabled={uploading}
                      aria-label={`Remove ${pf.file.name}`}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button
                onClick={handleUploadAll}
                disabled={uploading}
                className="w-full sm:w-auto"
              >
                {uploading ? "Uploading..." : `Upload ${pendingFiles.length} file${pendingFiles.length > 1 ? "s" : ""}`}
              </Button>
            </div>
          )}

          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => document.getElementById("file-upload")?.click()}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
              ${isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"}
            `}
          >
            <Upload className="h-10 w-10 mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm font-medium">
              {isDragging ? "Drop files here" : "Drag and drop files here, or click to browse"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              PDF, Word (.docx), Excel (.xlsx, .xls, .csv)
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Upload Entry Summary (PDF) and Commercial Invoice (XLSX) for best results.
            </p>
          </div>

          {uploadSuccess && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
              {uploadSuccess}
            </div>
          )}
        </CardContent>
      </Card>

      {loadWarnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700">
          {loadWarnings.includes("workflow") && <span>Could not load trust workflow. </span>}
          {loadWarnings.includes("analysis") && <span>Could not load analysis items. </span>}
          {loadWarnings.includes("items") && <span>Could not load shipment items. </span>}
          Some information may be incomplete.
        </div>
      )}

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
          <p className="text-sm text-amber-800">{error}</p>
          <p className="text-sm text-amber-800">
            Check that files are PDF, Word (.docx), or Excel (.xlsx, .xls, .csv) and under the size limit, then try uploading again.
          </p>
        </div>
      )}
      {clarificationError && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <p className="text-sm text-amber-800">{clarificationError}</p>
        </div>
      )}

      {preComplianceRows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{isPreCompliance ? "Pre-Compliance Clarifications" : "Optional Product Evidence"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {isPreCompliance && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 space-y-1">
                <p><strong>{totalCooCount} items detected</strong></p>
                <p>{totalCooCount - completedCooCount} of {totalCooCount} require Country of Origin</p>
                <p>Analysis is blocked until COO is completed for all items</p>
              </div>
            )}
            {preComplianceRows.map((row: any, idx: number) => {
              const itemId = row.itemId ? String(row.itemId) : ""
              const savedCoo = String(row.country_of_origin || "").toUpperCase()
              const hasSavedCoo = savedCoo.length === 2
              const label = row.label || `Item ${idx + 1}`
              const likelyHts = row.likelyHts
              const rowDoc = row.sourceDocId
                ? documents.find((d) => d.id === row.sourceDocId)
                : undefined
              const hasDataSheetEvidence =
                isDataSheetEvidenceReady(rowDoc) ||
                String(analysisItems[idx]?.supplemental_evidence_source || "").toLowerCase() === "amazon_url"
              const hasUrlEvidence =
                String(analysisItems[idx]?.supplemental_evidence_source || "").toLowerCase() === "amazon_url"
              const confidenceStage = !hasDataSheetEvidence
                ? "INITIAL"
                : hasDataSheetEvidence && !hasSavedCoo
                ? "IMPROVED"
                : hasDataSheetEvidence && hasSavedCoo && hasUrlEvidence
                ? "STRONG"
                : hasDataSheetEvidence && hasSavedCoo
                ? "IMPROVED"
                : "INITIAL"
              const htsAssuranceText = likelyHts
                ? `Most likely HS code from current evidence: ${likelyHts}`
                : hasDataSheetEvidence
                ? "Data sheet received. We have enough evidence for an initial classification pass."
                : "Most likely HS code from current evidence: Pending more document evidence"
              const isExpanded = expandedItems[row.key] ?? !hasSavedCoo
              const filteredCountryOptions = COUNTRY_OPTIONS
                .filter((c) => {
                  const q = String(countryOfOriginInput[row.key] || "").trim().toLowerCase()
                  if (!q) return true
                  return (
                    c.name.toLowerCase().includes(q) ||
                    c.alpha2.toLowerCase().includes(q) ||
                    c.alpha3.toLowerCase().includes(q)
                  )
                })
                .slice(0, 10)
              return (
                <div key={row.key} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      className="text-sm font-medium text-left"
                      onClick={() => setExpandedItems((s) => ({ ...s, [row.key]: !isExpanded }))}
                    >
                      Item {idx + 1} - {label}
                    </button>
                    <span className={`text-xs font-medium ${hasSavedCoo ? "text-green-700" : "text-amber-700"}`}>
                      {hasSavedCoo ? "COO saved" : "Required: Country of Origin"}
                    </span>
                  </div>
                  {isExpanded && (
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-slate-700 block">Required: Country of Origin</label>
                      <input
                        ref={(el) => { countryInputRefs.current[row.key] = el }}
                        type="text"
                        placeholder="Search country: South Korea, KR, or KOR"
                        value={countryOfOriginInput[row.key] ?? ""}
                        onChange={(e) =>
                          setCountryOfOriginInput((s) => ({
                            ...s,
                            [row.key]: e.target.value,
                          }))
                        }
                        onFocus={() => {
                          setCountryPickerOpenFor(row.key)
                          setCountryPickerHighlightIndex((s) => ({ ...s, [row.key]: 0 }))
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") {
                            setCountryPickerOpenFor(null)
                            return
                          }
                          if (!filteredCountryOptions.length) return
                          if (e.key === "ArrowDown") {
                            e.preventDefault()
                            setCountryPickerOpenFor(row.key)
                            setCountryPickerHighlightIndex((s) => ({
                              ...s,
                              [row.key]: Math.min(
                                (s[row.key] ?? -1) + 1,
                                filteredCountryOptions.length - 1
                              ),
                            }))
                          } else if (e.key === "ArrowUp") {
                            e.preventDefault()
                            setCountryPickerOpenFor(row.key)
                            setCountryPickerHighlightIndex((s) => ({
                              ...s,
                              [row.key]: Math.max((s[row.key] ?? 0) - 1, 0),
                            }))
                          } else if (e.key === "Enter" && countryPickerOpenFor === row.key) {
                            const idx = countryPickerHighlightIndex[row.key] ?? 0
                            const selected = filteredCountryOptions[idx]
                            if (selected) {
                              e.preventDefault()
                              setCountryOfOriginInput((s) => ({
                                ...s,
                                [row.key]: `${selected.name} (${selected.alpha2}/${selected.alpha3})`,
                              }))
                              setCountryPickerOpenFor(null)
                            }
                          }
                        }}
                        onBlur={() => setTimeout(() => setCountryPickerOpenFor((k) => (k === row.key ? null : k)), 120)}
                        className="w-full rounded border border-input bg-background px-3 py-2 text-sm"
                      />
                      {countryPickerOpenFor === row.key && (
                        <div className="max-h-40 overflow-y-auto rounded-md border border-slate-200 bg-white">
                          {filteredCountryOptions.map((c, optionIdx) => (
                              <button
                                key={c.alpha2}
                                type="button"
                                className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${
                                  (countryPickerHighlightIndex[row.key] ?? 0) === optionIdx ? "bg-slate-100" : ""
                                }`}
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => {
                                  setCountryOfOriginInput((s) => ({ ...s, [row.key]: `${c.name} (${c.alpha2}/${c.alpha3})` }))
                                  setCountryPickerOpenFor(null)
                                }}
                              >
                                {c.name} ({c.alpha2}/{c.alpha3})
                              </button>
                            ))}
                        </div>
                      )}
                      <Button
                        size="sm"
                        disabled={
                          supplementalSubmitting[row.key] ||
                          !(countryOfOriginInput[row.key] ?? "").trim()
                        }
                        onClick={async () => {
                          const value = normalizeCountryInput(countryOfOriginInput[row.key] ?? "")
                          if (!value) {
                            setClarificationError("Invalid country. Enter a country name, 2-letter ISO code (e.g. KR), or 3-letter code (e.g. KOR).")
                            return
                          }
                          setClarificationError(null)
                          setSupplementalSubmitting((s) => ({ ...s, [row.key]: true }))
                          try {
                            if (itemId) {
                              await apiPatch(`/api/v1/shipments/${shipmentId}/items/${itemId}`, {
                                country_of_origin: value,
                              })
                            } else {
                              await apiPost(`/api/v1/shipments/${shipmentId}/items`, {
                                label,
                                country_of_origin: value,
                              })
                            }
                            await loadAnalysisItems()
                            await loadShipmentItems()
                            setCountryOfOriginInput((s) => ({ ...s, [row.key]: value }))
                            const nextRow = preComplianceRows[idx + 1]
                            setExpandedItems((s) => ({
                              ...s,
                              [row.key]: false,
                              ...(nextRow ? { [nextRow.key]: true } : {}),
                            }))
                            if (nextRow) {
                              setTimeout(() => {
                                countryInputRefs.current[nextRow.key]?.focus()
                                setCountryPickerOpenFor(nextRow.key)
                                setCountryPickerHighlightIndex((s) => ({ ...s, [nextRow.key]: 0 }))
                              }, 0)
                            }
                          } catch (e: unknown) {
                            setClarificationError(formatApiError(e as ApiClientError))
                          } finally {
                            setSupplementalSubmitting((s) => ({ ...s, [row.key]: false }))
                          }
                        }}
                      >
                        {supplementalSubmitting[row.key] ? "Saving..." : "Save COO"}
                      </Button>
                    </div>
                  )}
                  <p className="text-xs text-[#334155]">
                    <strong>{htsAssuranceText}</strong>
                    {isPreCompliance && !hasSavedCoo ? " (provisional)" : ""}
                  </p>
                  {hasDataSheetEvidence ? (
                    <p className="text-xs text-muted-foreground">
                      Data sheet is usable for analysis (extracted text checks out, or you confirmed it below).
                    </p>
                  ) : (
                    <p className="text-xs text-amber-800">
                      No usable data sheet evidence yet. Run analysis once to extract text, map this document to a line
                      item, or confirm the data sheet in the Documents list.
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">Add a product URL only if you want higher certainty.</p>
                  <div className="flex flex-wrap gap-2 items-center">
                    <input
                      type="url"
                      placeholder="Optional: Amazon or product URL for higher certainty"
                      value={supplementalUrl[row.key] ?? ""}
                      onChange={(e) => setSupplementalUrl((s) => ({ ...s, [row.key]: e.target.value }))}
                      className="flex-1 min-w-[180px] rounded border border-input bg-background px-2 py-1.5 text-sm"
                      disabled={!itemId}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!itemId || supplementalSubmitting[row.key] || !(supplementalUrl[row.key] ?? "").trim()}
                      onClick={async () => {
                        const url = (supplementalUrl[row.key] ?? "").trim()
                        if (!itemId || !url) return
                        setSupplementalSubmitting((s) => ({ ...s, [row.key]: true }))
                        try {
                          await apiPost(`/api/v1/shipments/${shipmentId}/items/${itemId}/supplemental-evidence`, {
                            type: "amazon_url",
                            amazon_url: url,
                          })
                          setSupplementalUrl((s) => ({ ...s, [row.key]: "" }))
                          await loadAnalysisItems()
                        } catch (e: unknown) {
                          setError(formatApiError(e as ApiClientError))
                        } finally {
                          setSupplementalSubmitting((s) => ({ ...s, [row.key]: false }))
                        }
                      }}
                    >
                      {supplementalSubmitting[row.key] ? "Adding..." : "Save link"}
                    </Button>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Evidence posture: {confidenceStage === "STRONG" ? "Stronger" : confidenceStage === "IMPROVED" ? "Improved" : "Initial"}
                  </p>
                </div>
              )
            })}
            {isPreCompliance && (
              <div className="border-t pt-3 flex items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">{completedCooCount} of {totalCooCount} COO completed</p>
                <Button
                  disabled={!allCooComplete || !onRunPreComplianceAnalysis}
                  onClick={() => onRunPreComplianceAnalysis?.()}
                >
                  Run Pre-Compliance Analysis
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {unmatchedDocs.length > 0 && shipmentItems.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Unmapped documents</CardTitle>
            <p className="text-sm text-muted-foreground">
              These files are not linked to a line item. Link them so data sheets follow the correct SKU (filename
              matching is only a default).
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {unmatchedDocs.map((doc) => (
              <div key={doc.id} className="flex flex-wrap items-center gap-2 border rounded-md p-3">
                <span className="text-sm font-medium truncate flex-1 min-w-0">{doc.filename}</span>
                <label className="sr-only">Line item for {doc.filename}</label>
                <select
                  className="text-sm border rounded px-2 py-1.5 bg-background"
                  value={linkItemChoice[doc.id] || ""}
                  onChange={(e) => setLinkItemChoice((s) => ({ ...s, [doc.id]: e.target.value }))}
                  aria-label={`Line item for ${doc.filename}`}
                >
                  <option value="">Choose line item…</option>
                  {shipmentItems.map((it: any) => (
                    <option key={String(it.id)} value={String(it.id)}>
                      {it.label || it.id}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  disabled={!linkItemChoice[doc.id] || linkingDocId === doc.id}
                  onClick={async () => {
                    const itemId = linkItemChoice[doc.id]
                    if (!itemId) return
                    setLinkingDocId(doc.id)
                    setError(null)
                    try {
                      await apiPost(`/api/v1/shipments/${shipmentId}/item-document-links`, {
                        shipment_item_id: itemId,
                        shipment_document_id: doc.id,
                        mapping_status: "USER_CONFIRMED",
                      })
                      await loadTrustWorkflow()
                    } catch (e: unknown) {
                      setError(formatApiError(e as ApiClientError))
                    } finally {
                      setLinkingDocId(null)
                    }
                  }}
                >
                  {linkingDocId === doc.id ? "Linking…" : "Link"}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Documents List */}
      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : documents.length === 0 ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
              <p className="text-sm text-muted-foreground">
                Upload Entry Summary or Commercial Invoice to run analysis.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex flex-wrap items-center gap-3 p-3 border rounded-lg"
                >
                  <Button variant="ghost" size="sm" onClick={() => handleView(doc.id)} className="shrink-0">
                    View
                  </Button>
                  <DocumentIcon filename={doc.filename} />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{doc.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                    </p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      {doc.extraction_status
                        ? `Extraction: ${doc.extraction_status}`
                        : doc.processing_status && doc.processing_status !== "UPLOADED"
                          ? `Processing: ${doc.processing_status}`
                          : "Extraction: pending (runs with analysis)"}
                      {doc.char_count != null ? ` · ${doc.char_count} chars` : ""}
                      {doc.ocr_used ? " · OCR used" : ""}
                      {doc.usable_for_analysis === false ? " · Not usable for analysis" : ""}
                    </p>
                    {doc.extraction_status === "empty" && (
                      <p className="text-[11px] text-amber-700 font-medium mt-0.5">
                        No readable text extracted. This document cannot contribute to analysis.
                      </p>
                    )}
                    {doc.extraction_status === "success" && doc.char_count != null && doc.char_count < 100 && (
                      <p className="text-[11px] text-amber-700 mt-0.5">
                        Very little text extracted ({doc.char_count} chars). Classification quality may be low.
                      </p>
                    )}
                    {doc.ocr_used && doc.extraction_status === "success" && (
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        OCR was required. Extraction may contain errors.
                      </p>
                    )}
                    <div className="flex flex-wrap gap-2 mt-2">
                      {doc.document_type === "DATA_SHEET" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          disabled={Boolean(doc.data_sheet_user_confirmed)}
                          onClick={async () => {
                            setError(null)
                            try {
                              await apiPatch(`/api/v1/shipment-documents/${doc.id}/data-sheet-confirmation`, {
                                confirmed: true,
                              })
                              await loadDocuments()
                            } catch (e: unknown) {
                              setError(formatApiError(e as ApiClientError))
                            }
                          }}
                        >
                          {doc.data_sheet_user_confirmed
                            ? "Confirmed as evidence"
                            : "Confirm data sheet usable as evidence"}
                        </Button>
                      )}
                      {doc.extraction_status && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          disabled={reprocessingId === doc.id}
                          onClick={async () => {
                            setReprocessingId(doc.id)
                            setError(null)
                            try {
                              await apiPost(`/api/v1/shipment-documents/${doc.id}/reprocess`, {})
                              await loadDocuments()
                            } catch (e: unknown) {
                              setError(formatApiError(e as ApiClientError))
                            } finally {
                              setReprocessingId(null)
                            }
                          }}
                        >
                          {reprocessingId === doc.id ? "Reprocessing…" : "Re-extract"}
                        </Button>
                      )}
                    </div>
                  </div>
                  <span className="text-sm text-muted-foreground shrink-0" aria-label={`Type: ${documentTypeLabel(doc.document_type)}`}>
                    {documentTypeLabel(doc.document_type)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => handleDelete(doc.id, doc.filename)}
                    disabled={deletingId === doc.id}
                    title="Delete document"
                    aria-label={`Delete ${doc.filename}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
