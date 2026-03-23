/**
 * Documents Tab - Sprint 12
 * 
 * Document list + upload with S3 presigned flow.
 */

"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { Upload, FileText, FileSpreadsheet, Trash2, X } from "lucide-react"

interface DocumentsTabProps {
  shipment: any
  shipmentId: string
}

type DocumentType = "ENTRY_SUMMARY" | "COMMERCIAL_INVOICE" | "PACKING_LIST" | "DATA_SHEET"

interface ShipmentDocument {
  id: string
  document_type: string
  filename: string
  uploaded_at: string
  retention_expires_at: string
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

export function DocumentsTab({ shipment, shipmentId }: DocumentsTabProps) {
  const { apiGet, apiPost, apiPut, apiDelete } = useApiClient()
  const [documents, setDocuments] = useState<ShipmentDocument[]>([])
  const [analysisItems, setAnalysisItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [supplementalUrl, setSupplementalUrl] = useState<Record<string, string>>({})
  const [supplementalSubmitting, setSupplementalSubmitting] = useState<Record<string, boolean>>({})
  const [error, setError] = useState<string | null>(null)
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)

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
      setAnalysisItems(status?.result_json?.items || [])
    } catch {
      setAnalysisItems([])
    }
  }

  useEffect(() => {
    loadDocuments()
    loadAnalysisItems()
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
    setUploadSuccess(null)
    try {
      for (const pf of pendingFiles) {
        await uploadOne(pf)
      }
      setPendingFiles([])
      await loadDocuments()
      await loadAnalysisItems()
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
    try {
      await apiDelete(`/api/v1/shipment-documents/${docId}`)
      await loadDocuments()
      await loadAnalysisItems()
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setDeletingId(null)
    }
  }

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

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
          <p className="text-sm text-amber-800">{error}</p>
          <p className="text-sm text-amber-800">
            Check that files are PDF, Word (.docx), or Excel (.xlsx, .xls, .csv) and under the size limit, then try uploading again.
          </p>
        </div>
      )}

      {analysisItems.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Optional Product Evidence</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              For each line item, you can optionally add a product data sheet or Amazon/product link to strengthen evidence quality. Analysis is not blocked if you skip this.
            </p>
            {analysisItems.map((item: any, idx: number) => {
              const itemId = item.id ? String(item.id) : ""
              const needsMoreData = Boolean(item.needs_supplemental_evidence)
              const label = item.label || `Item ${idx + 1}`
              const pscAlt = item?.psc?.alternatives?.[0]
              const classPrimary = item?.classification?.primary_candidate
              const likelyHts = pscAlt?.alternative_hts_code || classPrimary?.hts_code || item?.hts_code || null
              return (
                <div key={itemId || `line-${idx}`} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{label}</p>
                    {needsMoreData ? (
                      <span className="text-xs text-amber-700 font-medium">
                        NECO could improve accuracy with more product information
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">Optional</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Do you have a data sheet or Amazon/product link for this line item?
                  </p>
                  <p className="text-xs text-[#334155]">
                    Most likely HS code{item?.hts_code ? " used in current analysis" : " from current evidence"}:{" "}
                    <strong>{likelyHts || "Pending more document evidence"}</strong>
                  </p>
                  <div className="flex flex-wrap gap-2 items-center">
                    <input
                      type="url"
                      placeholder="Amazon or product URL"
                      value={supplementalUrl[itemId] ?? ""}
                      onChange={(e) => setSupplementalUrl((s) => ({ ...s, [itemId]: e.target.value }))}
                      className="flex-1 min-w-[180px] rounded border border-input bg-background px-2 py-1.5 text-sm"
                      disabled={!itemId}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!itemId || supplementalSubmitting[itemId] || !(supplementalUrl[itemId] ?? "").trim()}
                      onClick={async () => {
                        const url = (supplementalUrl[itemId] ?? "").trim()
                        if (!itemId || !url) return
                        setSupplementalSubmitting((s) => ({ ...s, [itemId]: true }))
                        try {
                          await apiPost(`/api/v1/shipments/${shipmentId}/items/${itemId}/supplemental-evidence`, {
                            type: "amazon_url",
                            amazon_url: url,
                          })
                          setSupplementalUrl((s) => ({ ...s, [itemId]: "" }))
                          await loadAnalysisItems()
                        } catch (e: unknown) {
                          setError(formatApiError(e as ApiClientError))
                        } finally {
                          setSupplementalSubmitting((s) => ({ ...s, [itemId]: false }))
                        }
                      }}
                    >
                      {itemId && supplementalSubmitting[itemId] ? "Adding..." : "Save link"}
                    </Button>
                  </div>
                </div>
              )
            })}
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
