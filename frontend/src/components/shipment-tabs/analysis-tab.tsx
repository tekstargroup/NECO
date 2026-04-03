/**
 * Analysis Tab - Sprint 12
 * 
 * Start analysis, poll status, display results in 8-section order.
 */

"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusPill } from "@/components/ui/status-pill"
import { BlockerBox } from "@/components/ui/blocker-box"
import { WarningBox } from "@/components/ui/warning-box"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { AnalysisProgressTracker } from "@/components/analysis-progress-tracker"
import { RecommendationDetailDrawer } from "@/components/recommendation-detail-drawer"
import { GroundedChatBar } from "@/components/grounded-chat-bar"

/** Minimum time the analysis progress UI runs before showing results (trust / perceived work). */
const MIN_ANALYSIS_PROGRESS_MS = 10_000

interface AnalysisTabProps {
  shipment: any
  shipmentId: string
  autoStartAnalysis?: boolean
  onAutoStartComplete?: () => void
  onSwitchToReviews?: () => void
  onSwitchToDocuments?: () => void
  onSwitchToExports?: () => void
}

export function AnalysisTab({ shipment, shipmentId, autoStartAnalysis, onAutoStartComplete, onSwitchToReviews, onSwitchToDocuments, onSwitchToExports }: AnalysisTabProps) {
  const { apiGet, apiPost, apiPostForm, apiDelete } = useApiClient()
  const eligibility = shipment.eligibility || { eligible: false, missing_requirements: [], satisfied_path: null }
  const [analysisId, setAnalysisId] = useState<string | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<any>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadWarnings, setLoadWarnings] = useState<string[]>([])
  const [runStartTime, setRunStartTime] = useState<number | null>(null)
  const [checkingResults, setCheckingResults] = useState(false)
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null)
  const autoStartFiredRef = useRef(false)
  const analyzeAbortRef = useRef<AbortController | null>(null)
  const cancelRequestedRef = useRef(false)
  const [extractionPreview, setExtractionPreview] = useState<{ line_items_count: number; duty_total: number } | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [shipmentAlerts, setShipmentAlerts] = useState<any[]>([])
  /** Set when user starts Analyze in this tab; used to enforce min progress duration. Null = show existing results immediately on load. */
  const [analysisRunStartedAt, setAnalysisRunStartedAt] = useState<number | null>(null)
  /** When false, COMPLETE+result_json is held back so the progress chart can finish (min 10s from run start). */
  const [resultsGateOpen, setResultsGateOpen] = useState(true)
  /** Frozen seconds for the post-COMPLETE hold animation (remaining time until min duration). */
  const [holdProgressDuration, setHoldProgressDuration] = useState<number | null>(null)
  const [domainReadiness, setDomainReadiness] = useState<any>(null)
  const [derivedReviewState, setDerivedReviewState] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const fetchReadiness = async () => {
      try {
        const tw = await apiGet<any>(`/api/v1/shipments/${shipmentId}/trust-workflow`)
        if (!cancelled) {
          setDomainReadiness(tw?.domain_readiness || null)
          setDerivedReviewState(tw?.review?.state || null)
        }
      } catch {
        if (!cancelled) setLoadWarnings(prev => prev.includes("readiness") ? prev : [...prev, "readiness"])
      }
    }
    fetchReadiness()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipmentId, analysisStatus?.status])

  const handlePreviewExtraction = async () => {
    setPreviewLoading(true)
    setError(null)
    try {
      const result = await apiPost(`/api/v1/shipments/${shipmentId}/extract-preview`, {}) as { line_items_count: number; duty_total: number }
      setExtractionPreview({ line_items_count: result.line_items_count, duty_total: result.duty_total })
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setPreviewLoading(false)
    }
  }

  const loadStatus = async () => {
    setCheckingResults(true)
    setError(null)
    try {
      const status = await apiGet<any>(`/api/v1/shipments/${shipmentId}/analysis-status`)
      setAnalysisStatus((prev: any) => ({
        ...status,
        result_json: status.result_json ?? prev?.result_json,
      }))
      if (status?.analysis_id) setAnalysisId(status.analysis_id)
      setLastCheckedAt(Date.now())
    } catch (e: unknown) {
      if ((e as { status?: number })?.status !== 404) {
        setError(formatApiError(e as ApiClientError))
      }
    } finally {
      setCheckingResults(false)
    }
  }

  useEffect(() => {
    autoStartFiredRef.current = false
    setAnalysisRunStartedAt(null)
    setResultsGateOpen(true)
  }, [shipmentId])

  // GAP 10: Load PSC alerts for this shipment (shipment detail integration)
  useEffect(() => {
    let cancelled = false
    const loadAlerts = async () => {
      try {
        const data = await apiGet<{ items: any[] }>(`/api/v1/psc-radar/alerts?shipment_id=${shipmentId}`)
        if (!cancelled && data?.items) setShipmentAlerts(data.items)
      } catch {
        if (!cancelled) {
          setShipmentAlerts([])
          setLoadWarnings(prev => prev.includes("alerts") ? prev : [...prev, "alerts"])
        }
      }
    }
    loadAlerts()
    return () => { cancelled = true }
  }, [apiGet, shipmentId])

  // Initial load: fetch existing analysis status when tab mounts (so coming back to tab shows current state, does NOT start a new run)
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const status = await apiGet<any>(`/api/v1/shipments/${shipmentId}/analysis-status`)
        if (!cancelled) {
          setAnalysisStatus((prev: any) => ({
            ...status,
            result_json: status.result_json ?? prev?.result_json,
          }))
          if (status?.analysis_id) setAnalysisId(status.analysis_id)
        }
      } catch (e: unknown) {
        if (!cancelled && (e as { status?: number })?.status !== 404) {
          setError(formatApiError(e as ApiClientError))
        }
      }
    }
    load()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipmentId])

  // Open results only after at least MIN_ANALYSIS_PROGRESS_MS from run start (when this session started the run).
  useEffect(() => {
    if (analysisRunStartedAt == null) {
      setResultsGateOpen(true)
      return
    }
    const st = analysisStatus?.status
    if (st === "FAILED" || st === "REFUSED") {
      setResultsGateOpen(true)
      return
    }
    const rj = analysisStatus?.result_json
    if (st === "COMPLETE" && rj) {
      const deadline = analysisRunStartedAt + MIN_ANALYSIS_PROGRESS_MS
      const rem = deadline - Date.now()
      if (rem <= 0) {
        setResultsGateOpen(true)
        return
      }
      setResultsGateOpen(false)
      const t = setTimeout(() => setResultsGateOpen(true), rem)
      return () => clearTimeout(t)
    }
    if (st === "QUEUED" || st === "RUNNING") {
      setResultsGateOpen(false)
    }
  }, [analysisStatus?.status, analysisStatus?.result_json, analysisStatus?.analysis_id, analysisRunStartedAt])

  useEffect(() => {
    const complete = analysisStatus?.status === "COMPLETE" && Boolean(analysisStatus?.result_json)
    const holding = complete && analysisRunStartedAt != null && !resultsGateOpen
    if (holding) {
      setHoldProgressDuration((d) => {
        if (d != null) return d
        const rem = Math.max(1, Math.ceil((analysisRunStartedAt + MIN_ANALYSIS_PROGRESS_MS - Date.now()) / 1000))
        return rem
      })
    } else {
      setHoldProgressDuration(null)
    }
  }, [analysisStatus?.status, analysisStatus?.result_json, analysisRunStartedAt, resultsGateOpen])

  // Auto-start analysis only when user explicitly clicked "Analyze Shipment" in header (runs once; clearing flag so switching away and back does NOT re-run)
  useEffect(() => {
    if (!autoStartAnalysis || !eligibility.eligible) return
    if (autoStartFiredRef.current) return
    autoStartFiredRef.current = true
    onAutoStartComplete?.()
    handleAnalyze()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStartAnalysis])

  // Poll analysis status every 2s while running so we show results as soon as the backend completes.
  useEffect(() => {
    if (!analysisId) return

    let cancelled = false
    let pollInterval: ReturnType<typeof setInterval>

    const poll = async () => {
      try {
        const status = await apiGet<any>(`/api/v1/shipments/${shipmentId}/analysis-status`)
        if (cancelled) return
        setAnalysisStatus((prev: any) => ({
          ...status,
          result_json: status.result_json ?? prev?.result_json,
        }))

        if (
          status.status === "COMPLETE" ||
          status.status === "FAILED" ||
          status.status === "REFUSED"
        ) {
          setAnalyzing(false)
          setRunStartTime(null)
          if (status.status === "FAILED" || status.status === "REFUSED") {
            setResultsGateOpen(true)
          }
          clearInterval(pollInterval)
          return
        }
        if (status.status === "RUNNING" || status.status === "QUEUED") {
          setRunStartTime((t) => t ?? Date.now())
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(formatApiError(e as ApiClientError))
          setAnalyzing(false)
          clearInterval(pollInterval)
        }
      }
    }

    poll()
    pollInterval = setInterval(poll, 2000)

    return () => {
      cancelled = true
      clearInterval(pollInterval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId, shipmentId])

  const handleAnalyze = async (forceNew = false, body?: Record<string, unknown>) => {
    if (analyzing) return
    if (analysisStatus?.status === "RUNNING" && !forceNew) return
    const endpoint = `/api/v1/shipments/${shipmentId}/analyze${forceNew ? "?force_new=1" : ""}`
    if (typeof window !== "undefined") {
      console.log("[NECO] Analyze clicked, sending POST to", endpoint)
    }
    setAnalyzing(true)
    setError(null)
    setAnalysisRunStartedAt(Date.now())
    setResultsGateOpen(false)
    setHoldProgressDuration(null)
    setAnalysisStatus(null)
    setRunStartTime(null)
    setLastCheckedAt(null)
    cancelRequestedRef.current = false
    const ANALYZE_TIMEOUT_MS = 5 * 60 * 1000 // 5 minutes so sync analysis can finish
    const controller = new AbortController()
    analyzeAbortRef.current = controller
    const timeoutId = setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS)

    const stuckFallbackMs = 5 * 60 * 1000
    const stuckFallbackId = setTimeout(() => {
      setAnalyzing(false)
      if (typeof window !== "undefined") {
        console.log("[NECO] Analyze request took >5 min; button re-enabled so you can try Re-run (start fresh).")
      }
    }, stuckFallbackMs)

    try {
      const response = await apiPost<{
        analysis_id?: string
        status: string
        sync?: boolean
        result_json?: unknown
        [k: string]: unknown
      }>(endpoint, body ?? undefined, { signal: controller.signal })
      clearTimeout(stuckFallbackId)
      clearTimeout(timeoutId)
      analyzeAbortRef.current = null
      setAnalysisId(response.analysis_id ?? null)
      if (response.sync) {
        setAnalysisStatus(response)
        setAnalyzing(false)
        if (response.status === "FAILED" || response.status === "REFUSED") {
          setResultsGateOpen(true)
        }
      } else {
        setAnalysisStatus({ status: response.status })
      }
    } catch (e: unknown) {
      clearTimeout(stuckFallbackId)
      clearTimeout(timeoutId)
      analyzeAbortRef.current = null
      const err = e as ApiClientError & { name?: string }
      if (err?.name === "AbortError") {
        if (cancelRequestedRef.current) {
          setError("Analysis cancelled. The server may still be running analysis—click \"Check for results\" to see status, or Re-run to start again.")
        } else {
          setError("Analysis is taking longer than 5 minutes. Click \"Check for results\" below to see if it finished on the server, or Re-run to try again.")
        }
      } else {
        setError(formatApiError(e as ApiClientError))
      }
      setAnalyzing(false)
      setResultsGateOpen(true)
    }
  }

  const handleCancelAnalyze = () => {
    cancelRequestedRef.current = true
    analyzeAbortRef.current?.abort()
  }

  const isHoldProgressPhase =
    analysisStatus?.status === "COMPLETE" &&
    Boolean(analysisStatus?.result_json) &&
    !resultsGateOpen &&
    analysisRunStartedAt != null
  const holdEstimatedSeconds =
    isHoldProgressPhase && analysisRunStartedAt != null
      ? holdProgressDuration ??
        Math.max(1, Math.ceil((analysisRunStartedAt + MIN_ANALYSIS_PROGRESS_MS - Date.now()) / 1000))
      : null

  return (
    <div className="space-y-6">
      {/* Eligibility Panel */}
      {!eligibility.eligible && (
        <div className="space-y-3">
          <BlockerBox
            title="Analysis cannot run yet"
            blockers={eligibility.missing_requirements || []}
          />
          {onSwitchToDocuments && (eligibility.missing_requirements || []).some((m: string) =>
            /country of origin|missing coo/i.test(String(m))
          ) && (
            <Button size="sm" variant="outline" onClick={onSwitchToDocuments}>
              Go to Documents to complete COO
            </Button>
          )}
        </div>
      )}

      {/* Single Analysis card: status, actions, eligibility, warnings */}
      {eligibility.eligible && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <CardTitle className="text-base">Analysis</CardTitle>
                <span className="text-xs text-muted-foreground">
                  Requirement path: {eligibility.satisfied_path?.replace(/_/g, " ") || "—"}
                </span>
                {analysisStatus && (
                  <>
                    <StatusPill status={analysisStatus.status} />
                    {(analysisStatus.status === "FAILED" || analysisStatus.status === "REFUSED" || analysisStatus.status === "COMPLETE") && (
                      <Button size="sm" variant="outline" onClick={() => void handleAnalyze(true)} disabled={analyzing}>
                        {analyzing ? "Starting..." : "Re-run"}
                      </Button>
                    )}
                  </>
                )}
              </div>
              {!analysisStatus && (
                <Button onClick={() => void handleAnalyze()} disabled={analyzing}>
                  {analyzing ? "Starting..." : "Analyze Shipment"}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {/* Extraction preview: only before first analysis or when re-running */}
            {analysisStatus?.status !== "COMPLETE" && (shipment?.documents?.length ?? 0) > 0 && (
              <div className="mb-4 flex items-center gap-2">
                {extractionPreview ? (
                  <span className="text-sm text-muted-foreground">
                    {extractionPreview.line_items_count} line item{extractionPreview.line_items_count !== 1 ? "s" : ""} / ${extractionPreview.duty_total.toLocaleString()} duty (from Entry Summary)
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void handlePreviewExtraction()}
                    disabled={previewLoading || analyzing}
                    className="text-muted-foreground"
                  >
                    {previewLoading ? "Extracting…" : "Preview extraction"}
                  </Button>
                )}
              </div>
            )}
            {analysisStatus && (
              <div className="space-y-4">
                {(analysisStatus.status === "QUEUED" ||
                  analysisStatus.status === "RUNNING" ||
                  (analysisStatus.status === "COMPLETE" &&
                    analysisStatus.result_json &&
                    !resultsGateOpen &&
                    analysisRunStartedAt != null)) && (
                  <div className="space-y-3">
                    {(analysisStatus.status === "QUEUED" || analysisStatus.status === "RUNNING") ? (
                      <p className="text-xs text-muted-foreground">
                        Analysis runs in the background. You can leave this page and come back—results will show here when ready.
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Analysis finished on the server. Finishing the progress view before showing results…
                      </p>
                    )}
                    <div className="rounded-lg border bg-card p-6 space-y-4">
                      <AnalysisProgressTracker
                        key={isHoldProgressPhase ? `hold-${analysisRunStartedAt}` : "running"}
                        serverStatus={isHoldProgressPhase ? "COMPLETE" : analysisStatus?.status}
                        estimatedTotalSeconds={
                          holdEstimatedSeconds != null
                            ? holdEstimatedSeconds
                            : Math.max(
                                180,
                                ((shipment?.documents?.length || 0) + (shipment?.items?.length || 1)) * 45 + 120
                              )
                        }
                        onCompletedStepClick={() =>
                          document.getElementById("analysis-results")?.scrollIntoView({ behavior: "smooth" })
                        }
                      />
                      {(analysisStatus.status === "QUEUED" || analysisStatus.status === "RUNNING") && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={handleCancelAnalyze}
                          disabled={!analyzing}
                          className="text-muted-foreground"
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                    {(analysisStatus.status === "QUEUED" || analysisStatus.status === "RUNNING") &&
                    (runStartTime != null && Date.now() - runStartTime > 4 * 60 * 1000 ? (
                      <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 space-y-3">
                        <p className="text-sm font-medium text-amber-900">
                          Analysis is taking longer than expected. If it’s been more than 4 minutes, the server may be stuck.
                        </p>
                        <p className="text-xs text-amber-800">
                          Click <strong>Re-run analysis</strong> to start a fresh run (this cancels the current one). Or <strong>Check for results</strong> to see if it finished without restarting.
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => void handleAnalyze(true)}
                          >
                            {analyzing ? "Starting…" : "Re-run analysis (start fresh)"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void loadStatus()}
                            disabled={checkingResults}
                          >
                            {checkingResults ? "Checking…" : "Check for results (does not re-run)"}
                          </Button>
                        </div>
                        {lastCheckedAt != null && (
                          <p className="text-xs text-amber-800 mt-2">
                            Last checked {new Date(lastCheckedAt).toLocaleTimeString()}. Server status: <strong>{analysisStatus?.status ?? "—"}</strong>
                          </p>
                        )}
                      </div>
                    ) : (
                      <>
                        <p className="text-sm text-muted-foreground">
                          Typical run: 1–3 minutes. If nothing appears after about 4 minutes, click <strong>Re-run analysis (start fresh)</strong> below to try again.
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => void handleAnalyze(true)}
                          >
                            {analyzing ? "Starting…" : "Re-run analysis (start fresh)"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void loadStatus()}
                            disabled={analyzing || checkingResults}
                            title="Only checks the server for results; does not re-run analysis"
                          >
                            {checkingResults ? "Checking…" : "Check for results (does not re-run)"}
                          </Button>
                        </div>
                        {lastCheckedAt != null && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Last checked {new Date(lastCheckedAt).toLocaleTimeString()}. Server status: <strong>{analysisStatus?.status ?? "—"}</strong>
                          </p>
                        )}
                      </>
                    ))}
                  </div>
                )}

                {analysisStatus.refusal_reason_code && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
                    <p className="font-medium text-sm text-amber-900">
                      Analysis refused: {analysisStatus.refusal_reason_code}
                    </p>
                    {analysisStatus.refusal_reason_text && (
                      <p className="text-sm text-amber-800">{analysisStatus.refusal_reason_text}</p>
                    )}
                    <p className="text-sm text-amber-800">
                      Fix any issues above, then use <strong>Re-run</strong> to try again.
                    </p>
                    <Button size="sm" onClick={() => void handleAnalyze(true)} disabled={analyzing}>
                      {analyzing ? "Starting..." : "Re-run"}
                    </Button>
                  </div>
                )}

                {analysisStatus.error_message && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
                    <p className="font-medium text-sm text-amber-900">Analysis failed</p>
                    <p className="text-sm text-amber-800">{analysisStatus.error_message}</p>
                    <p className="text-sm text-amber-800 font-medium">What you can do:</p>
                    <ul className="text-sm text-amber-800 list-disc list-inside space-y-1">
                      <li>In the <strong>Documents</strong> tab, set each file’s type (Entry Summary or Commercial Invoice).</li>
                      <li>Ensure at least one Entry Summary (PDF) and one Commercial Invoice (Excel/CSV) are uploaded.</li>
                      <li>Re-run analysis below to re-scan and import line items.</li>
                    </ul>
                    <Button size="sm" onClick={() => void handleAnalyze(true)} disabled={analyzing}>
                      {analyzing ? "Starting..." : "Re-run"}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
          <p className="text-sm text-amber-800">{error}</p>
          <p className="text-sm text-amber-800">
            Check your connection and that the backend is running. Then try again.
          </p>
          <Button size="sm" variant="outline" onClick={() => setError(null)}>
            Dismiss
          </Button>
        </div>
      )}

      {loadWarnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700">
          {loadWarnings.includes("readiness") && <span>Could not load readiness data. </span>}
          {loadWarnings.includes("alerts") && <span>Could not load regulatory alerts. </span>}
          Some information may be incomplete.
        </div>
      )}

      {/* Scroll target for "Completed" step click; results render below when ready */}
      <div id="analysis-results" className="scroll-mt-4" aria-hidden />
      {analysisStatus?.status === "COMPLETE" && !analysisStatus?.result_json && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-amber-900">
              Analysis is complete but results are still loading.
            </p>
            <p className="mt-1 text-sm text-amber-800">
              Click <strong>Check for results</strong> below to load them—it does not re-run analysis. If they don’t appear after a few tries, use Re-run to start a new analysis.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void loadStatus()}
              disabled={checkingResults}
              className="mt-3"
              title="Only checks the server; does not re-run"
            >
              {checkingResults ? "Checking…" : "Check for results (does not re-run)"}
            </Button>
            {lastCheckedAt != null && (
              <p className="text-xs text-muted-foreground mt-2">
                Last checked {new Date(lastCheckedAt).toLocaleTimeString()}. Status: <strong>{analysisStatus?.status ?? "—"}</strong>
              </p>
            )}
          </CardContent>
        </Card>
      )}
      {analysisStatus?.result_json && resultsGateOpen && (
        <div className="space-y-6">
          {(() => {
            const items = analysisStatus.result_json?.items || []
            const hasDocWithTable = (analysisStatus.result_json?.evidence_map?.documents || []).some(
              (d: any) => d.table_preview && Array.isArray(d.table_preview) && d.table_preview.length > 0
            )
            const showSelectionCard = items.length === 0 || hasDocWithTable
            return showSelectionCard ? (
              <NoLineItemsCard
                resultJson={analysisStatus.result_json}
                shipmentId={shipmentId}
                eligibility={eligibility}
                analyzing={analyzing}
                shipmentStatus={shipment.status}
                onReRun={() => void handleAnalyze(true)}
                onSelectionDone={() => void loadStatus()}
                apiPost={apiPost}
                hasExistingItems={items.length > 0}
              />
            ) : null
          })()}
          <AnalysisResultsView
            resultJson={analysisStatus.result_json}
            shipmentId={shipmentId}
            shipment={shipment}
            shipmentAlerts={shipmentAlerts}
            apiGet={apiGet}
            apiPost={apiPost}
            apiPostForm={apiPostForm}
            apiDelete={apiDelete}
            onRefresh={() => void loadStatus()}
            onReRunWithClarifications={(responses) => void handleAnalyze(true, { clarification_responses: responses })}
            onReRun={() => void handleAnalyze(true)}
            analyzing={analyzing}
            onSwitchToReviews={onSwitchToReviews}
            onSwitchToDocuments={onSwitchToDocuments}
            onSwitchToExports={onSwitchToExports}
            derivedReviewState={derivedReviewState}
            domainReadiness={domainReadiness}
          />
          <GroundedChatBar
            shipmentId={shipmentId}
            items={analysisStatus.result_json?.items || []}
          />
        </div>
      )}
    </div>
  )
}

const COLUMN_FIELD_ALIASES: Record<string, string[]> = {
  description: ["description", "product", "item", "name", "commodity", "part", "article"],
  htsCode: ["hts", "hs code", "tariff", "harmonized", "hs codes"],
  quantity: ["quantity", "qty", "units", "unit number", "unit qty", "qty shipped"],
  unitPrice: ["unit price", "price", "rate", "unit cost", "price per unit"],
  countryOfOrigin: ["country of origin", "origin", "coo", "country", "country of origin"],
}

function detectColumnMapping(columns: string[]): Record<string, string> {
  const colLower = columns.map((c) => ({ orig: c, lower: String(c).toLowerCase() }))
  const out: Record<string, string> = {}
  for (const [field, aliases] of Object.entries(COLUMN_FIELD_ALIASES)) {
    for (const { orig, lower } of colLower) {
      if (aliases.some((a) => lower.includes(a) || a.includes(lower))) {
        out[field] = orig
        break
      }
    }
  }
  return out
}

const COLUMN_MAPPING_STORAGE_KEY = "neco_line_item_column_mapping"

function loadStoredColumnMapping(filename: string): Record<string, string> | null {
  if (typeof window === "undefined") return null
  try {
    const raw = localStorage.getItem(COLUMN_MAPPING_STORAGE_KEY)
    if (!raw) return null
    const all = JSON.parse(raw) as Record<string, Record<string, string>>
    return all[filename] || all["*"] || null
  } catch {
    return null
  }
}

function saveColumnMapping(filename: string, mapping: Record<string, string>) {
  if (typeof window === "undefined") return
  try {
    const raw = localStorage.getItem(COLUMN_MAPPING_STORAGE_KEY)
    const all = (raw ? JSON.parse(raw) : {}) as Record<string, Record<string, string>>
    all[filename] = mapping
    all["*"] = mapping
    localStorage.setItem(COLUMN_MAPPING_STORAGE_KEY, JSON.stringify(all))
  } catch {
    // ignore
  }
}

/** Map a raw table row (e.g. from Excel) to API shape. Uses column mapping when provided, else auto-detects. */
function rowToSelectionItem(
  row: Record<string, unknown>,
  mapping?: {
    descriptionColumn?: string
    htsCodeColumn?: string
    quantityColumn?: string
    countryColumn?: string
    unitPriceColumn?: string
  }
): {
  description?: string
  quantity?: number
  total?: number
  unit_price?: number
  hts_code?: string
  country_of_origin?: string
} {
  const get = (... cand: string[]) => {
    for (const c of cand) {
      const key = Object.keys(row).find((k) => k.toLowerCase().includes(c) || c.includes(k.toLowerCase()))
      if (key != null) {
        const v = row[key]
        if (v !== undefined && v !== null && String(v).trim() !== "") return v
      }
    }
    return undefined
  }
  const num = (v: unknown): number | undefined => {
    if (v === undefined || v === null) return undefined
    const n = Number(v)
    return Number.isFinite(n) ? n : undefined
  }
  const str = (v: unknown): string | undefined =>
    v === undefined || v === null ? undefined : String(v).trim() || undefined
  const fromCol = (col?: string) => (col && row[col] != null ? str(row[col]) : undefined)
  const fromColNum = (col?: string) => (col && row[col] != null ? num(row[col]) : undefined)
  const desc = mapping?.descriptionColumn ? fromCol(mapping.descriptionColumn) : str(get("description", "product", "item", "name", "commodity")) ?? str(row["Description"] ?? row["description"])
  const qty = mapping?.quantityColumn ? fromColNum(mapping.quantityColumn) : num(get("qty", "quantity", "units") ?? row["Qty"] ?? row["Quantity"])
  const total = num(get("total", "extended", "value", "amount") ?? row["Extended Value"] ?? row["Total"] ?? row["Value"])
  const unitPrice = mapping?.unitPriceColumn ? fromColNum(mapping.unitPriceColumn) : num(get("unit price", "price", "rate") ?? row["Unit Price"] ?? row["Price"])
  return {
    description: desc,
    quantity: qty,
    total: total ?? (unitPrice != null && qty != null ? unitPrice * qty : undefined),
    unit_price: unitPrice,
    hts_code: mapping?.htsCodeColumn ? fromCol(mapping.htsCodeColumn) : str(get("hts", "hs code", "tariff") ?? row["HS Codes"] ?? row["HTS"]),
    country_of_origin: mapping?.countryColumn ? fromCol(mapping.countryColumn) : str(get("country", "origin", "coo") ?? row["Country of Origin"] ?? row["Origin"]),
  }
}

function NoLineItemsCard({
  resultJson,
  shipmentId,
  eligibility,
  analyzing,
  shipmentStatus,
  onReRun,
  onSelectionDone,
  apiPost,
  hasExistingItems = false,
}: {
  resultJson: any
  shipmentId: string
  eligibility: { eligible: boolean }
  analyzing: boolean
  shipmentStatus: string
  onReRun: () => void
  onSelectionDone: () => void
  apiPost: (path: string, body: unknown) => Promise<unknown>
  hasExistingItems?: boolean
}) {
  const docs = resultJson?.evidence_map?.documents || []
  const docWithTable = docs.find((d: any) => d.table_preview && Array.isArray(d.table_preview) && d.table_preview.length > 0)
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())
  const [submitting, setSubmitting] = useState(false)
  const [selectionSuccess, setSelectionSuccess] = useState<string | null>(null)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [descriptionColumn, setDescriptionColumn] = useState<string>("")
  const [htsCodeColumn, setHtsCodeColumn] = useState<string>("")
  const [quantityColumn, setQuantityColumn] = useState<string>("")
  const [unitPriceColumn, setUnitPriceColumn] = useState<string>("")
  const [countryColumn, setCountryColumn] = useState<string>("")
  const [tablePage, setTablePage] = useState(0)
  const [showTable, setShowTable] = useState(!hasExistingItems)

  const rows = docWithTable?.table_preview?.slice(0, 100) || []
  const columns = docWithTable?.table_columns || (rows[0] ? Object.keys(rows[0]) : [])
  const filename = docWithTable?.filename || ""
  const ROWS_PER_PAGE = 8
  const totalPages = Math.max(1, Math.ceil(rows.length / ROWS_PER_PAGE))
  const paginatedRows = rows.slice(tablePage * ROWS_PER_PAGE, (tablePage + 1) * ROWS_PER_PAGE)
  const columnMapping = {
    descriptionColumn: descriptionColumn || undefined,
    htsCodeColumn: htsCodeColumn || undefined,
    quantityColumn: quantityColumn || undefined,
    unitPriceColumn: unitPriceColumn || undefined,
    countryColumn: countryColumn || undefined,
  }

  // Pre-select columns from auto-detect + stored preferences; pre-select all data rows
  useEffect(() => {
    if (columns.length === 0) return
    const detected = detectColumnMapping(columns)
    const stored = loadStoredColumnMapping(filename)
    const apply = (key: string, setter: (v: string) => void) => {
      const val = stored?.[key] ?? detected[key]
      if (val && columns.includes(val)) setter(val)
    }
    apply("description", setDescriptionColumn)
    apply("htsCode", setHtsCodeColumn)
    apply("quantity", setQuantityColumn)
    apply("unitPrice", setUnitPriceColumn)
    apply("countryOfOrigin", setCountryColumn)
  }, [columns.join(","), filename])

  const hasPreSelectedRef = useRef(false)
  const prevDocRef = useRef<string>("")
  useEffect(() => {
    const docKey = `${filename}:${rows.length}`
    if (docKey !== prevDocRef.current) {
      prevDocRef.current = docKey
      hasPreSelectedRef.current = false
    }
    if (rows.length > 0 && !hasPreSelectedRef.current) {
      hasPreSelectedRef.current = true
      const headerKeywords = ["qty", "part no", "description", "country of origin", "eccn", "hs codes", "unit price", "extended value", "exporter", "ship from", "invoice no", "invoice date"]
      const looksLikeHeader = (row: Record<string, unknown>) =>
        Object.values(row).some((v) => {
          const s = String(v ?? "").toLowerCase()
          return headerKeywords.some((kw) => s === kw || s.startsWith(kw + "\n") || s.endsWith("\n" + kw))
        })
      const hasNumeric = (row: Record<string, unknown>) =>
        Object.values(row).some((v) => typeof v === "number" && Number.isFinite(v))
      const lineItemIndices = rows
        .map((row: Record<string, unknown>, i: number) => {
          if (looksLikeHeader(row)) return -1
          const vals = Object.values(row)
          const hasContent = vals.some((v) => v !== undefined && v !== null && String(v).trim() !== "")
          if (!hasContent) return -1
          if (hasNumeric(row)) return i
          return -1
        })
        .filter((i: number) => i >= 0)
      const toSelect = lineItemIndices.length > 0 ? lineItemIndices : rows
        .map((row: Record<string, unknown>, i: number) => (Object.values(row).some((v) => v !== undefined && v !== null && String(v).trim() !== "") ? i : -1))
        .filter((i: number) => i >= 0)
      setSelectedRows(new Set(toSelect))
    }
  }, [rows.length, filename])

  const toggleRow = (i: number) => {
    setSelectedRows((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  const selectAll = () => {
    if (selectedRows.size === rows.length) setSelectedRows(new Set())
    else setSelectedRows(new Set(rows.map((_: any, i: number) => i)))
  }

  const handleUseSelected = async () => {
    if (selectedRows.size === 0) return
    setSubmitting(true)
    setSelectionSuccess(null)
    setSelectionError(null)
    try {
      const items = Array.from(selectedRows)
        .sort((a, b) => a - b)
        .map((i) => rowToSelectionItem(rows[i] as Record<string, unknown>, columnMapping))
      await apiPost(`/api/v1/shipments/${shipmentId}/line-items-from-selection`, { items, replace_items: hasExistingItems })
      saveColumnMapping(filename, {
        description: descriptionColumn || "",
        htsCode: htsCodeColumn || "",
        quantity: quantityColumn || "",
        unitPrice: unitPriceColumn || "",
        countryOfOrigin: countryColumn || "",
      })
      setSelectionSuccess(hasExistingItems ? "Line items replaced. Click Re-run above to run analysis." : "Line items added. Click Re-run above to run analysis with them.")
      setSelectedRows(new Set())
      onSelectionDone()
    } catch (e: unknown) {
      setSelectionSuccess(null)
      setSelectionError(formatApiError(e as ApiClientError) || "Failed to save selected rows")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="border-amber-200 bg-amber-50/50">
      <CardContent className="pt-6 space-y-4">
        {resultJson?.no_items_hint === "files_not_found" ? (
          <>
            <p className="text-sm font-medium text-amber-900">
              Document files weren’t found on the server for this run.
            </p>
            <p className="text-sm text-amber-800">
              Re-upload your <strong>Entry Summary</strong> (PDF) and <strong>Commercial Invoice</strong> (Excel/CSV) in the <strong>Documents</strong> tab, set each file’s type, then click <strong>Re-run</strong> below so the next run uses the new uploads.
            </p>
          </>
        ) : (
          <>
            {docWithTable ? (
              <>
                <p className="text-sm font-medium text-amber-900">
                  {hasExistingItems
                    ? <>Map columns and select rows from <strong>{docWithTable.filename}</strong> to replace line items, then click &quot;Replace with selected rows&quot; and Re-run.</>
                    : <>No line items were auto-imported. Select which rows from <strong>{docWithTable.filename}</strong> are line items below, then click &quot;Use selected rows&quot; to add them and run analysis again.</>
                  }
                </p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-amber-900">
                  No line items in this analysis.
                </p>
                <p className="text-sm text-amber-800 mt-1">
                  In the <strong>Documents</strong> tab: upload an <strong>Entry Summary</strong> (PDF) and a <strong>Commercial Invoice</strong> (Excel or CSV). Set each file’s type (dropdown → Save). Then click <strong>Re-run</strong> below so we can extract and import line items.
                </p>
                {docs.length > 0 && (
                  <p className="text-sm text-amber-800 mt-1">
                    You have {docs.length} document(s) but none had extractable line items. If one is an Excel/CSV invoice, set its type to <strong>Commercial Invoice</strong> and Re-run.
                  </p>
                )}
              </>
            )}
            {resultJson?.evidence_map?.extraction_errors?.length > 0 && (
              <p className="text-sm text-amber-800 mt-2">
                Some documents had extraction errors. Fix document types in the Documents tab and Re-run.
              </p>
            )}
            {docWithTable && (
              <div className="space-y-3 mt-4">
                {(selectionSuccess || (hasExistingItems && !showTable)) ? (
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-green-200 bg-green-50 p-3">
                    <div className="flex items-center gap-2">
                      <span className="text-green-600 text-lg" aria-hidden>✓</span>
                      <div>
                        <p className="text-sm font-medium text-green-800">
                          {selectionSuccess || (hasExistingItems ? "Line items confirmed. Re-run above to analyze." : "Selection complete.")}
                        </p>
                        <p className="text-xs text-green-700 mt-0.5">Row/column selection done.</p>
                      </div>
                    </div>
                    <button type="button" onClick={() => { setSelectionSuccess(null); setShowTable(true) }} className="text-xs underline text-green-700 hover:text-green-900">Change selection</button>
                  </div>
                ) : (
                  <>
                    {selectionError && (
                      <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{selectionError}</div>
                    )}
                    <div className="flex flex-wrap gap-3 items-center text-sm">
                      <label className="flex items-center gap-1.5">
                        <span className="text-muted-foreground text-xs">Item name:</span>
                        <select
                          value={descriptionColumn}
                          onChange={(e) => setDescriptionColumn(e.target.value)}
                          disabled={submitting}
                          className="rounded border border-input bg-background px-1.5 py-0.5 text-xs disabled:opacity-50"
                        >
                          <option value="">—</option>
                          {columns.map((col: string) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </label>
                      <label className="flex items-center gap-1.5">
                        <span className="text-muted-foreground text-xs">HS Code:</span>
                        <select
                          value={htsCodeColumn}
                          onChange={(e) => setHtsCodeColumn(e.target.value)}
                          disabled={submitting}
                          className="rounded border border-input bg-background px-1.5 py-0.5 text-xs disabled:opacity-50"
                        >
                          <option value="">—</option>
                          {columns.map((col: string) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </label>
                      <label className="flex items-center gap-1.5">
                        <span className="text-muted-foreground text-xs">COO:</span>
                        <select
                          value={countryColumn}
                          onChange={(e) => setCountryColumn(e.target.value)}
                          disabled={submitting}
                          className="rounded border border-input bg-background px-1.5 py-0.5 text-xs disabled:opacity-50"
                        >
                          <option value="">—</option>
                          {columns.map((col: string) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </label>
                      <label className="flex items-center gap-1.5">
                        <span className="text-muted-foreground text-xs">Quantity:</span>
                        <select
                          value={quantityColumn}
                          onChange={(e) => setQuantityColumn(e.target.value)}
                          disabled={submitting}
                          className="rounded border border-input bg-background px-1.5 py-0.5 text-xs disabled:opacity-50"
                        >
                          <option value="">—</option>
                          {columns.map((col: string) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </label>
                      <label className="flex items-center gap-1.5">
                        <span className="text-muted-foreground text-xs">Unit price:</span>
                        <select
                          value={unitPriceColumn}
                          onChange={(e) => setUnitPriceColumn(e.target.value)}
                          disabled={submitting}
                          className="rounded border border-input bg-background px-1.5 py-0.5 text-xs disabled:opacity-50"
                        >
                          <option value="">—</option>
                          {columns.map((col: string) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="overflow-x-auto border rounded-md bg-white max-w-2xl max-h-48 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-muted">
                          <tr>
                            <th className="p-1 text-left w-8">
                              <button type="button" onClick={selectAll} className="text-xs underline">
                                {selectedRows.size === rows.length ? "Clear" : "All"}
                              </button>
                            </th>
                            {columns.map((col: string) => (
                              <th key={col} className="p-1 text-left font-medium max-w-[120px] truncate" title={String(col)}>{String(col)}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {paginatedRows.map((row: Record<string, unknown>, idx: number) => {
                            const i = tablePage * ROWS_PER_PAGE + idx
                            return (
                              <tr key={i} className="border-t border-border">
                                <td className="p-1">
                                  <input
                                    type="checkbox"
                                    checked={selectedRows.has(i)}
                                    onChange={() => toggleRow(i)}
                                    aria-label={`Select row ${i + 1}`}
                                    className="scale-90"
                                  />
                                </td>
                                {columns.map((col: string) => (
                                  <td key={col} className="p-1 max-w-[120px] truncate" title={String((row as any)[col] ?? "")}>{String((row as any)[col] ?? "")}</td>
                                ))}
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    {totalPages > 1 && (
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground">Page {tablePage + 1} of {totalPages}</span>
                        <button type="button" onClick={() => setTablePage((p) => Math.max(0, p - 1))} disabled={tablePage === 0} className="underline disabled:opacity-50">Prev</button>
                        <button type="button" onClick={() => setTablePage((p) => Math.min(totalPages - 1, p + 1))} disabled={tablePage >= totalPages - 1} className="underline disabled:opacity-50">Next</button>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2 items-center">
                      <Button
                        size="sm"
                        onClick={handleUseSelected}
                        disabled={submitting || selectedRows.size === 0}
                      >
                        {submitting ? (hasExistingItems ? "Replacing…" : "Adding…") : `Use selected (${selectedRows.size} row${selectedRows.size !== 1 ? "s" : ""})`}
                      </Button>
                      {hasExistingItems && (
                        <button type="button" onClick={() => setShowTable(false)} className="text-xs text-muted-foreground underline">Done</button>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </>
        )}
        {eligibility.eligible && (
          <Button onClick={() => onReRun()} disabled={analyzing}>
            {analyzing ? "Starting..." : "Re-run"}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

const WHAT_WAS_NOT_EVALUATED = [
  "Trade program eligibility (e.g. GSP, preference programs)",
  "Country-specific preferences",
  "Quota or safeguard measures",
  "Legal interpretation of HTSUS notes",
  "Valuation method",
  "Origin rules beyond declared country of origin",
]

/** Decisive copy per spec — not vague */
const STATUS_LABELS: Record<string, string> = {
  SUCCESS: "Confident",
  REVIEW_REQUIRED: "Review recommended before export",
  NO_CONFIDENT_MATCH: "Best alternative identified. Review recommended.",
  CLARIFICATION_REQUIRED: "Answer a few questions to narrow down",
  NO_GOOD_MATCH: "Review recommended",
}

function _parseValue(val: any): number {
  if (val == null) return 0
  if (typeof val === "number" && !Number.isNaN(val)) return val
  const n = parseFloat(String(val).replace(/[^0-9.-]/g, ""))
  return Number.isNaN(n) ? 0 : n
}

/** Surface backend reason with neutral language. Never overstate certainty. */
function _reframeReason(raw: string | undefined, altHts: string | undefined, _isPreCompliance = false): string {
  const s = (raw || "").trim()
  if (s && s.length <= 120) return s
  if (s) return s.slice(0, 117) + "…"
  return altHts
    ? "Alternative HTS suggested — review before accepting."
    : "Review recommended."
}

function AnalysisResultsView({
  resultJson,
  shipmentId,
  shipment = {},
  shipmentAlerts = [],
  apiGet,
  apiPost,
  apiPostForm,
  apiDelete,
  onRefresh,
  onReRunWithClarifications,
  onReRun,
  analyzing,
  onSwitchToReviews,
  onSwitchToDocuments,
  onSwitchToExports,
  derivedReviewState,
  domainReadiness,
}: {
  resultJson: any
  shipmentId?: string
  shipment?: any
  shipmentAlerts?: any[]
  apiGet?: (path: string) => Promise<unknown>
  apiPost?: (path: string, body: unknown) => Promise<unknown>
  apiPostForm?: (path: string, formData: FormData) => Promise<unknown>
  apiDelete?: (path: string) => Promise<unknown>
  onRefresh?: () => void
  onReRunWithClarifications?: (responses: Record<string, Record<string, string>>) => void
  onReRun?: () => void
  analyzing?: boolean
  onSwitchToReviews?: () => void
  onSwitchToDocuments?: () => void
  onSwitchToExports?: () => void
  derivedReviewState?: string | null
  domainReadiness?: any
}) {
  const shipmentTypeRef = (shipment?.references || []).find((r: any) => String(r?.key || "").toUpperCase() === "SHIPMENT_TYPE")
  const shipmentType = String(shipmentTypeRef?.value || "PRE_COMPLIANCE").toUpperCase()
  const isPreCompliance = shipmentType !== "ENTRY_COMPLIANCE"
  const warnings = resultJson?.warnings || []
  const blockers = resultJson?.blockers || []
  const items = resultJson?.items || []
  const reviewStatus = derivedReviewState || resultJson?.review_status || "DRAFT"
  const hasClarificationQuestions = items.some((i: any) => (i.classification?.questions || i.clarification_questions || []).length > 0)
  const [supplementalUrl, setSupplementalUrl] = useState<Record<string, string>>({})
  const [supplementalSubmitting, setSupplementalSubmitting] = useState<Record<string, boolean>>({})
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, Record<string, string>>>({} as Record<string, Record<string, string>>)
  const [drawerItem, setDrawerItem] = useState<any | null>(null)
  const [evidenceBundle, setEvidenceBundle] = useState<any | null>(null)

  // Fetch evidence bundle when drawer opens
  useEffect(() => {
    if (!drawerItem || !shipmentId || !apiGet) {
      setEvidenceBundle(null)
      return
    }
    const raw = items[drawerItem.index]
    const itemId = raw?.id
    if (!itemId) {
      setEvidenceBundle(null)
      return
    }
    let cancelled = false
    apiGet(`/api/v1/shipments/${shipmentId}/analysis/items/${itemId}/evidence`)
      .then((bundle: any) => { if (!cancelled) setEvidenceBundle(bundle) })
      .catch(() => { if (!cancelled) { setEvidenceBundle(null); console.warn("[NECO] Could not load evidence bundle for item", itemId) } })
    return () => { cancelled = true }
  }, [drawerItem, shipmentId, items, apiGet])

  // Build view model for decision UI; add line labels when same product appears multiple times
  const productNameCounts = new Map<string, number>()
  items.forEach((item: any) => {
    const name = item.label || ""
    if (name) productNameCounts.set(name, (productNameCounts.get(name) ?? 0) + 1)
  })
  const viewItems = items.map((item: any, idx: number) => {
    const duty = item.duty
    const dutyFromEs = item.duty_from_entry_summary
    const pscAlts = item.psc?.alternatives || []
    const candidates = item.classification?.candidates || []
    const primary = item.classification?.primary_candidate
    const customsValue = _parseValue(item.value) || _parseValue(item.entered_value) || (item.unit_value != null && item.quantity != null ? _parseValue(item.unit_value) * _parseValue(item.quantity) : 0)
    const dutyPaid = dutyFromEs && (dutyFromEs.amount != null || dutyFromEs.section_301_amount != null)
      ? (dutyFromEs.amount ?? 0) + (dutyFromEs.section_301_amount ?? 0)
      : null
    const declaredRate = duty?.resolved_general_raw ? parseFloat(String(duty.resolved_general_raw).replace("%", "")) / 100 : null
    const bestAlt = pscAlts[0] || primary || candidates[0]
    const altRate = bestAlt?.alternative_duty_rate || bestAlt?.duty_rate_general
    const altHts =
      bestAlt?.alternative_hts_code ||
      bestAlt?.hts_code ||
      item?.classification?.likely_hts ||
      item?.classification?.suggested_hts ||
      item?.likely_hts ||
      item?.suggested_hts ||
      null
    const altRateNum = altRate ? parseFloat(String(altRate).replace("%", "")) / 100 : null
    const altEst = customsValue > 0 && altRateNum != null ? altRateNum * customsValue : (pscAlts[0]?.delta_amount ?? null)
    const deltaAmount = pscAlts[0]?.delta_amount ?? (altRateNum != null && declaredRate != null && customsValue > 0 ? (declaredRate - altRateNum) * customsValue : null)
    const deltaPct = pscAlts[0]?.delta_percent ?? (declaredRate != null && altRateNum != null && declaredRate > 0 ? ((declaredRate - altRateNum) / declaredRate) * 100 : null)
    const status = item.classification?.status || "TRADE_ACTION"
    const confidence = item.classification?.metadata?.analysis_confidence ?? null
    const baseName = item.label || `Item ${idx + 1}`
    const dupCount = productNameCounts.get(baseName) ?? 0
    const displayName = dupCount > 1 ? `${baseName} · Line ${idx + 1}` : baseName
    return {
      ...item,
      index: idx,
      productName: baseName,
      displayName,
      declaredHts: item.hts_code || "—",
      hasDeclaredHts: Boolean(item.hts_code),
      countryOfOrigin: item.country_of_origin || "—",
      currentDutyRate: duty?.resolved_general_raw || duty?.resolved_special_raw || "Pending duty resolution",
      dutyScenarios: item.duty_scenarios,
      classificationMemo: item.classification_memo,
      recommendedHts: altHts,
      estimatedSavings: deltaAmount != null && deltaAmount > 0 ? deltaAmount : (altEst != null ? altEst : 0),
      estimatedSavingsPct: deltaPct,
      confidence,
      risk: blockers.length > 0 ? "Medium" : "Low",
      shortReason: _reframeReason(item.psc?.summary, altHts, isPreCompliance),
      evidenceSources: ["Entry Summary", "Commercial Invoice"],
      likelyHts:
        altHts ||
        item?.classification?.primary_candidate?.hts_code ||
        item?.classification?.candidates?.[0]?.hts_code ||
        item.hts_code ||
        null,
      hasAuthorityRef: Boolean(item?.classification?.candidates?.some((c: any) => c?.legal_basis || c?.source || c?.ruling)),
      hasSignalRef: Boolean(item?.psc?.alternatives?.length || item?.regulatory?.length),
      priorKnowledge: item.prior_knowledge || null,
    }
  })

  const ALWAYS_VISIBLE_LEVELS = ["no_classification", "needs_input", "insufficient_support"]
  const visibleRows = isPreCompliance
    ? viewItems
    : viewItems.filter((i: any) =>
        i.recommendedHts ||
        i.estimatedSavings > 0 ||
        ALWAYS_VISIBLE_LEVELS.includes(i.classificationMemo?.support_level)
      )
  const attentionItems = viewItems.filter((i: any) =>
    ALWAYS_VISIBLE_LEVELS.includes(i.classificationMemo?.support_level)
  )
  const totalPotentialSavings = viewItems.reduce((sum: number, i: any) => sum + (i.estimatedSavings || 0), 0)
  const itemsWithRecommendations = viewItems.filter((i: any) => i.recommendedHts).length
  const actionableReviewCount = viewItems.filter((i: any) => i.recommendedHts || (i.estimatedSavings || 0) > 0).length
  const hasAnyDeclaredHts = viewItems.some((i: any) => i.hasDeclaredHts)
  const reviewRequiredCount = blockers.length > 0 ? items.length : (reviewStatus === "REVIEW_REQUIRED" ? items.length : itemsWithRecommendations || 0)
  const confidenceValues = viewItems.map((i: any) => i.confidence).filter((c: any) => c != null && typeof c === "number")
  const overallConfidence = confidenceValues.length > 0 ? confidenceValues.reduce((s: number, c: number) => s + c, 0) / confidenceValues.length : null
  const overallRisk = blockers.length > 0 ? "Medium" : "Low"
  const recommendedAction = reviewRequiredCount > 0 ? `Review ${reviewRequiredCount} HTS change${reviewRequiredCount !== 1 ? "s" : ""}` : "Ready to export"

  // Extract regulatory flags (FDA, LACEY, etc.) from blockers, warnings, and shipment alerts for prominent display
  const regulatoryFlags = Array.from(new Set([
    ...blockers.map((b: any) => (typeof b === "string" ? b : b?.message || "")),
    ...warnings.map((w: any) => (typeof w === "string" ? w : w?.message || "")),
    ...shipmentAlerts.filter((a: any) => /FDA|LACEY|Lacey|import.?restriction|regulatory/i.test(a.alert_type || a.reason || "")).map((a: any) => `${a.alert_type || "Regulatory"}: ${a.reason || "requires review"}`),
  ].filter((s: string) => s && /FDA|LACEY|Lacey|regulatory|requires review/i.test(s))))
  const showVerifiedBanner = actionableReviewCount === 0 && regulatoryFlags.length === 0 && blockers.length === 0
  const canOpenReviews = Boolean(onSwitchToReviews) && actionableReviewCount > 0
  const handleOpenReviews = () => {
    if (!onSwitchToReviews) return
    const firstFlagged = viewItems.find((i: any) => i.recommendedHts || (i.estimatedSavings || 0) > 0)
    if (typeof window !== "undefined" && firstFlagged) {
      window.sessionStorage.setItem(
        "neco_reviews_focus",
        JSON.stringify({ index: firstFlagged.index, ts: Date.now() })
      )
    }
    onSwitchToReviews()
  }

  return (
    <>
    <div className="space-y-6" id="analysis-results">
      {/* Readiness strip — backend-derived, per-domain */}
      {domainReadiness && (
        <div className="flex flex-wrap gap-3 text-xs">
          {[
            { key: "documents", icon: "Docs", ready: domainReadiness.documents?.ready },
            { key: "items", icon: "Items", ready: domainReadiness.items?.all_ready },
            { key: "classification", icon: "Classification", ready: domainReadiness.classification?.state === "generated" },
            { key: "duty", icon: "Duty", ready: domainReadiness.duty?.available },
            { key: "regulatory", icon: "Regulatory", ready: domainReadiness.regulatory?.signals_available },
          ].map((d) => (
            <div
              key={d.key}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 border ${
                d.ready
                  ? "border-green-200 bg-green-50 text-green-800"
                  : "border-slate-200 bg-slate-50 text-slate-600"
              }`}
            >
              <span className="font-medium">{d.icon}</span>
              <span>{domainReadiness[d.key]?.label || "—"}</span>
            </div>
          ))}
        </div>
      )}

      {/* 1. Sticky header */}
      <div className="sticky top-0 z-30 bg-background/95 backdrop-blur border-b px-6 py-4 -mx-6 -mt-2 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{shipment?.name || "Shipment"}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {resultJson?.generated_at ? `Analysis: ${new Date(resultJson.generated_at).toLocaleString()}` : ""}
            {reviewStatus && ` · ${reviewStatus.replace(/_/g, " ")}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canOpenReviews && (
            <Button onClick={handleOpenReviews} size="sm" className="font-medium">
              {reviewRequiredCount > 0 ? `Review ${reviewRequiredCount} Items` : "Review Items"}
            </Button>
          )}
          {onSwitchToExports && (
            <Button onClick={onSwitchToExports} variant="secondary" size="sm">
              Export Summary to Broker
            </Button>
          )}
          {onReRun && (
            <Button onClick={onReRun} variant="ghost" size="sm" disabled={analyzing}>
              {analyzing ? "Re-running…" : "Re-run Analysis"}
            </Button>
          )}
        </div>
      </div>

      {/* Needs Attention — above everything when blocked items exist */}
      {attentionItems.length > 0 && (
        <div className="rounded-xl border-2 border-amber-300 bg-amber-50/60 shadow-sm p-5 mt-4 space-y-3">
          <div>
            <h2 className="text-lg font-semibold text-amber-900">Needs Attention ({attentionItems.length})</h2>
            <p className="text-xs text-amber-800 mt-0.5">These items require input or cannot be reliably classified.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {attentionItems.map((ai: any) => {
              const level = ai.classificationMemo?.support_level
              const itemId = ai.id || items[ai.index]?.id
              const answers = clarificationAnswers[itemId] || {}
              const openQs = ai.classificationMemo?.open_questions || []
              const allAnswered = openQs.length > 0 && openQs.every((q: any) => {
                const attr = typeof q === "string" ? q : q?.attribute
                return attr && answers[attr]?.trim()
              })
              return (
                <div
                  key={ai.index}
                  className={`rounded-lg border p-3 text-sm ${
                    level === "no_classification" ? "border-red-200 bg-red-50/60" :
                    level === "needs_input" ? "border-amber-200 bg-amber-50/60" :
                    "border-slate-200 bg-slate-50/60"
                  }`}
                >
                  <p className="font-medium text-slate-900 truncate">{ai.displayName}</p>
                  {ai.declaredHts && ai.declaredHts !== "—" && (
                    <p className="text-xs text-slate-500 font-mono">{ai.declaredHts}</p>
                  )}
                  <p className={`text-xs mt-1 ${level === "no_classification" ? "text-red-700" : "text-amber-800"}`}>
                    {ai.classificationMemo?.summary || (
                      level === "no_classification"
                        ? "Cannot generate a reliable classification from current evidence."
                        : level === "needs_input"
                        ? "Additional product facts required before classification."
                        : "Classification has insufficient support — verify independently."
                    )}
                  </p>
                  {level === "needs_input" && openQs.length > 0 && (
                    <div className="mt-2 space-y-1.5" onClick={(e) => e.stopPropagation()}>
                      {openQs.slice(0, 3).map((q: any, qi: number) => {
                        const attr = typeof q === "string" ? q : q?.attribute
                        const question = typeof q === "string" ? q : q?.question || q?.attribute || "—"
                        return (
                          <div key={qi}>
                            <label className="block text-[10px] font-medium text-slate-600">{question}</label>
                            <input
                              type="text"
                              className="w-full rounded border border-slate-300 px-2 py-0.5 text-xs"
                              placeholder="Your answer…"
                              value={answers[attr] || ""}
                              onChange={(e) => setClarificationAnswers((prev) => ({
                                ...prev,
                                [itemId]: { ...(prev[itemId] || {}), [attr]: e.target.value },
                              }))}
                            />
                          </div>
                        )
                      })}
                      {onReRunWithClarifications && (
                        <Button
                          size="sm" variant="default" className="mt-1 text-xs"
                          disabled={!allAnswered || analyzing}
                          onClick={() => onReRunWithClarifications(clarificationAnswers)}
                        >
                          {analyzing ? "Re-running…" : "Answer & re-run"}
                        </Button>
                      )}
                    </div>
                  )}
                  {level === "no_classification" && onSwitchToDocuments && (
                    <Button size="sm" variant="outline" className="mt-2 text-xs" onClick={() => onSwitchToDocuments()}>
                      Upload / map documents
                    </Button>
                  )}
                  {level === "insufficient_support" && (
                    <Button size="sm" variant="outline" className="mt-2 text-xs" onClick={() => setDrawerItem(ai)}>
                      Review evidence
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Import summary (when available) */}
      {resultJson?.import_summary &&
        (resultJson.import_summary.imported > 0 ||
          resultJson.import_summary.merged > 0 ||
          (resultJson.import_summary.conflicts?.length ?? 0) > 0 ||
          (resultJson.import_summary.provenance_skipped?.length ?? 0) > 0) && (
        <div className="rounded-md border border-blue-200 bg-blue-50/60 px-4 py-2.5 text-xs text-blue-900">
          <strong>Import results:</strong>{" "}
          {resultJson.import_summary.imported > 0 && <span>{resultJson.import_summary.imported} added</span>}
          {resultJson.import_summary.merged > 0 && <span>{resultJson.import_summary.imported > 0 ? ", " : ""}{resultJson.import_summary.merged} merged</span>}
          {resultJson.import_summary.skipped > 0 && <span>, {resultJson.import_summary.skipped} unchanged</span>}
          {resultJson.import_summary.conflicts?.length > 0 && (
            <span className="text-amber-700 font-medium">, {resultJson.import_summary.conflicts.length} conflict{resultJson.import_summary.conflicts.length !== 1 ? "s" : ""}</span>
          )}
          {(resultJson.import_summary.provenance_skipped?.length ?? 0) > 0 && (
            <span className="text-amber-700 font-medium">
              {(resultJson.import_summary.imported > 0 || resultJson.import_summary.merged > 0 || (resultJson.import_summary.conflicts?.length ?? 0) > 0) ? ", " : ""}
              {resultJson.import_summary.provenance_skipped.length} line
              {resultJson.import_summary.provenance_skipped.length !== 1 ? "s" : ""} with no line provenance (HTS mismatch — document line not merged)
            </span>
          )}
          {resultJson.import_summary.conflicts?.length > 0 && (
            <details className="mt-1">
              <summary className="cursor-pointer text-amber-700">View conflicts</summary>
              <ul className="mt-1 space-y-0.5 text-[11px]">
                {resultJson.import_summary.conflicts.map((c: any, ci: number) => (
                  <li key={ci}>
                    <span className="font-mono">{c.existing_hts}</span> (existing: {c.existing_label}) vs{" "}
                    <span className="font-mono">{c.incoming_hts}</span> (incoming: {c.incoming_label}) — {c.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {(resultJson.import_summary.provenance_skipped?.length ?? 0) > 0 && (
            <details className="mt-1">
              <summary className="cursor-pointer text-amber-700">Why some lines have no provenance</summary>
              <ul className="mt-1 space-y-0.5 text-[11px]">
                {resultJson.import_summary.provenance_skipped.map((p: { line_num: number; reason: string }, pi: number) => (
                  <li key={pi}>
                    Line <span className="font-mono">{p.line_num}</span> — {p.reason === "hts_conflict" ? "HTS conflict: incoming line could not be merged with an existing item, so structured line provenance was not attached." : p.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* 2. Narrative header — single clear sentence, then Confidence + Risk */}
      <div className="rounded-xl border-2 border-primary/20 bg-card shadow-sm p-5 mt-6">
        <h2 className="text-xl font-semibold">
          {isPreCompliance
            ? itemsWithRecommendations > 0
              ? `${itemsWithRecommendations} item${itemsWithRecommendations !== 1 ? "s" : ""} with likely HS classifications identified`
              : "Pre-compliance classification analysis generated"
            : totalPotentialSavings > 0
            ? `You may have overpaid $${totalPotentialSavings.toLocaleString()} across ${itemsWithRecommendations} item${itemsWithRecommendations !== 1 ? "s" : ""}`
            : itemsWithRecommendations > 0
            ? `${itemsWithRecommendations} item${itemsWithRecommendations !== 1 ? "s" : ""} with alternative classifications identified`
            : "No alternative classifications with material duty difference"}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {itemsWithRecommendations > 0
            ? isPreCompliance
              ? `Suggested HS codes are shown below${overallConfidence != null ? ` with ${overallConfidence >= 0.7 ? "higher" : overallConfidence >= 0.5 ? "moderate" : "lower"} model-reported evidence strength` : ""}. Not a legal determination.`
              : `Alternative HTS suggestions are shown below. Review before export.`
            : hasAnyDeclaredHts
            ? "No alternative identified from available evidence."
            : "No declared HTS provided. Showing classification suggestions from available evidence."}
        </p>
        <div className="flex flex-wrap gap-4 mt-4">
          <span>
            <strong>Evidence strength (model):</strong>{" "}
            {overallConfidence == null ? "Unknown" : overallConfidence >= 0.7 ? "Higher" : overallConfidence >= 0.5 ? "Moderate" : "Lower"}
          </span>
          <span><strong>Risk:</strong> {overallRisk}</span>
        </div>
      </div>

      {showVerifiedBanner && (
        <div className="rounded-lg border border-green-200 bg-green-50/80 px-4 py-3">
          <p className="text-sm font-semibold text-green-900">No issues detected</p>
          <p className="text-sm text-green-800 mt-1">
            {isPreCompliance
              ? "NECO did not identify reclassification concerns or regulatory flags for this shipment."
              : "NECO did not identify alternative classifications with material duty difference or regulatory flags."}
          </p>
          <ul className="text-sm text-green-800 mt-2 list-disc list-inside">
            <li>{hasAnyDeclaredHts ? "No alternative identified for the declared HTS." : "No declared HTS was provided for comparison."}</li>
            <li>{isPreCompliance ? "Classification suggestions are based on currently available evidence." : "No material duty difference was identified from the available evidence."}</li>
            <li>Review is still recommended before filing.</li>
          </ul>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          DOMAIN 1: CLASSIFICATION (always shown)
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-2xl border bg-card shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-muted/30">
          <h3 className="font-semibold">{isPreCompliance ? "Classification Suggestions" : "Classification Analysis"}</h3>
          <p className="text-[11px] text-muted-foreground/80 mt-0.5">
            Classification suggestions are not legal determinations. Confirm with your broker before filing.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F8FAFC]">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Item</th>
                <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Declared HTS</th>
                <th className="px-4 py-3 text-left font-medium text-[#0F172A]">{isPreCompliance ? "Likely HS suggestion" : "Suggested HTS"}</th>
                <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Evidence strength</th>
                <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Evidence / Reason</th>
                <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.length > 0 ? (
                [...visibleRows]
                  .sort((a: any, b: any) => (b.estimatedSavings || 0) - (a.estimatedSavings || 0))
                  .map((vi: any, rowIdx: number) => (
                    <tr
                      key={vi.index}
                      className={`border-t border-[#E5E7EB] hover:bg-[#F8FAFC] cursor-pointer ${rowIdx % 2 === 1 ? "bg-[#F8FAFC]/50" : ""} ${ALWAYS_VISIBLE_LEVELS.includes(vi.classificationMemo?.support_level) ? "opacity-50" : ""}`}
                      onClick={() => setDrawerItem(vi)}
                    >
                      {(() => {
                        const memoLevel = vi.classificationMemo?.support_level
                        const isNoClassification = memoLevel === "no_classification"
                        const isInsufficient = memoLevel === "insufficient_support"
                        const isNeedsInput = memoLevel === "needs_input"
                        const isSuppressed = isNoClassification || isNeedsInput
                        const dutyUnavailable = vi.dutyScenarios?.unavailable || (!vi.duty && isSuppressed)

                        if (isSuppressed) {
                          return (
                            <>
                              <td className="px-4 py-4 text-left font-medium text-[#0F172A]">{vi.displayName}</td>
                              <td className="px-4 py-4 text-left font-mono text-xs text-[#0F172A]">{vi.declaredHts}</td>
                              <td colSpan={4} className="px-4 py-4">
                                <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-2">
                                  <p className="text-sm font-medium text-slate-800">
                                    {isNoClassification
                                      ? "Cannot generate a reliable classification"
                                      : "Additional product facts required"}
                                  </p>
                                  <p className="text-xs text-slate-600 mt-0.5">
                                    {vi.classificationMemo?.summary || "Insufficient product evidence for classification."}
                                  </p>
                                </div>
                              </td>
                            </>
                          )
                        }

                        return (
                          <>
                            <td className="px-4 py-4 text-left">
                              <span className="font-medium text-[#0F172A]">{vi.displayName}</span>
                              {vi.priorKnowledge && (
                                <div className="mt-1 rounded bg-blue-50 border border-blue-200 px-2 py-1 text-[10px] text-blue-800">
                                  <span className="font-semibold">Prior classification found:</span>{" "}
                                  {vi.priorKnowledge.prior_hts_code}
                                  {vi.priorKnowledge.accepted_by && <span> (accepted by {vi.priorKnowledge.accepted_by})</span>}
                                  <span className="block text-blue-600 mt-0.5">Review before applying — not auto-applied</span>
                                </div>
                              )}
                            </td>
                            <td className="px-4 py-4 text-left font-mono text-xs text-[#0F172A]">{vi.declaredHts}</td>
                            <td className={`px-4 py-4 text-left font-mono text-xs font-bold ${isInsufficient ? "text-slate-400 line-through" : "text-[#0F172A]"}`}>
                              {vi.recommendedHts || "—"}
                              {isInsufficient && vi.recommendedHts && (
                                <span className="block text-[10px] text-slate-500 font-normal no-underline mt-0.5">Unreliable — verify independently</span>
                              )}
                            </td>
                            <td className="px-4 py-4 text-left">
                              <span
                                className={`inline-flex px-2 py-0.5 rounded text-xs ${
                                  isInsufficient || memoLevel === "weak_support"
                                    ? "bg-gray-100 text-gray-800"
                                    : vi.confidence >= 0.7
                                      ? "bg-green-100 text-green-800"
                                      : vi.confidence >= 0.5
                                        ? "bg-amber-100 text-amber-800"
                                        : "bg-gray-100 text-gray-700"
                                }`}
                              >
                                {vi.classificationMemo?.support_label ||
                                  (vi.confidence == null ? "Unknown" : vi.confidence >= 0.7 ? "High (model)" : vi.confidence >= 0.5 ? "Moderate (model)" : "Low (model)")}
                              </span>
                            </td>
                            <td className="px-4 py-4 text-left text-[#64748B] text-sm max-w-[320px]">
                              <p>{vi.shortReason}</p>
                              {vi.evidence_used?.length > 0 && (
                                <div className="mt-1 space-y-1">
                                  {vi.evidence_used.slice(0, 2).map((ev: any, evi: number) => (
                                    <div key={evi} className="text-[10px] text-slate-600 leading-snug">
                                      <span className="inline-flex rounded bg-blue-50 text-blue-700 px-1 py-0.5 mr-1">{ev.document_type?.replace(/_/g, " ") || "Doc"}</span>
                                      <span className={`inline-flex rounded px-1 py-0.5 mr-1 ${
                                        ev.match_confidence === "high" ? "bg-green-50 text-green-700" :
                                        ev.match_confidence === "medium" ? "bg-slate-100 text-slate-600" :
                                        "bg-amber-50 text-amber-700"
                                      }`}>
                                        {ev.match_confidence === "high" ? "Match: HIGH" :
                                         ev.match_confidence === "medium" ? "Match: MED" :
                                         "Match: LOW (filename)"}
                                      </span>
                                      {ev.filename}{ev.snippet ? `: "${ev.snippet.slice(0, 80)}…"` : ""}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {!(vi.evidence_used?.length > 0) && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  <span className="inline-flex rounded-full bg-blue-50 text-blue-700 px-2 py-0.5 text-[10px]">Doc evidence</span>
                                  {vi.hasAuthorityRef && (
                                    <span className="inline-flex rounded-full bg-purple-50 text-purple-700 px-2 py-0.5 text-[10px]">Authority</span>
                                  )}
                                </div>
                              )}
                              {!vi.declaredHts || vi.declaredHts === "—" ? (
                                <p className="mt-1 text-xs text-[#334155]">
                                  Most likely HS code: <strong>{vi.likelyHts || "Pending more evidence"}</strong>
                                </p>
                              ) : null}
                            </td>
                            <td className="px-4 py-4 text-left" onClick={(e) => e.stopPropagation()}>
                              <div className="flex flex-wrap gap-1">
                                {onSwitchToReviews && !isInsufficient && (
                                  <>
                                    <Button size="sm" variant="default" onClick={handleOpenReviews}>Accept</Button>
                                    <Button size="sm" variant="outline" onClick={handleOpenReviews}>Override</Button>
                                  </>
                                )}
                                <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); setDrawerItem(vi); }}>
                                  Explain
                                </Button>
                              </div>
                            </td>
                          </>
                        )
                      })()}
                    </tr>
                  ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">
                    {items.length > 0
                      ? hasAnyDeclaredHts
                        ? (isPreCompliance
                            ? "No higher-priority HS code suggestions identified. Declared HTS appears consistent."
                            : "No alternative classifications with material duty difference. Declared HTS appears consistent.")
                        : "No declared HTS provided. Initial likely HS classifications are shown from available evidence."
                      : "Upload documents and run analysis."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <RecommendationDetailDrawer
          open={!!drawerItem}
          onClose={() => setDrawerItem(null)}
          item={drawerItem || {}}
          isPreCompliance={isPreCompliance}
          rawItem={drawerItem ? items[drawerItem.index] : undefined}
          evidenceMap={resultJson?.evidence_map}
          evidenceBundle={evidenceBundle}
        />
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          DOMAIN 2: DUTY COMPARISON (hidden when no items have supported classification)
          ═══════════════════════════════════════════════════════════════════ */}
      {(() => {
        const dutyEligible = visibleRows.filter((vi: any) => {
          const level = vi.classificationMemo?.support_level
          const hasDeclaredHts = vi.hasDeclaredHts
          return (level === "supported" || hasDeclaredHts) && !(vi.dutyScenarios?.unavailable)
        })
        if (dutyEligible.length === 0) return null
        return (
          <div className="rounded-2xl border bg-card shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/30">
              <h3 className="font-semibold">Duty Impact Comparison</h3>
              <p className="text-[11px] text-muted-foreground/80 mt-0.5">
                Duty estimates are approximations based on MFN rates. Verify amounts with your licensed broker before filing.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC]">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Item</th>
                    <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Declared HTS</th>
                    <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Suggested HTS</th>
                    <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Declared duty (MFN est.)</th>
                    {!isPreCompliance && <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Est. Savings</th>}
                    <th className="px-4 py-3 text-left font-medium text-[#0F172A]">COO</th>
                    <th className="px-4 py-3 text-left font-medium text-[#0F172A]">Basis</th>
                  </tr>
                </thead>
                <tbody>
                  {dutyEligible.map((vi: any, rowIdx: number) => (
                    <tr
                      key={vi.index}
                      className={`border-t border-[#E5E7EB] hover:bg-[#F8FAFC] ${rowIdx % 2 === 1 ? "bg-[#F8FAFC]/50" : ""}`}
                    >
                      <td className="px-4 py-4 text-left font-medium text-[#0F172A]">{vi.displayName}</td>
                      <td className="px-4 py-4 text-left font-mono text-xs">{vi.declaredHts}</td>
                      <td className="px-4 py-4 text-left font-mono text-xs font-bold">{vi.recommendedHts || "—"}</td>
                      <td className="px-4 py-4 text-left text-xs">
                        <div>Rate: <strong>{vi.currentDutyRate}</strong></div>
                        {vi.dutyScenarios && !vi.dutyScenarios.unavailable && (
                          <div className="mt-1 text-[10px] text-slate-600 leading-snug">
                            Declared: {vi.dutyScenarios.declared_hts || "—"} · Suggested: {vi.dutyScenarios.suggested_hts || "—"}
                          </div>
                        )}
                      </td>
                      {!isPreCompliance && (
                        <td className="px-4 py-4 text-left font-bold text-green-700">
                          {vi.estimatedSavings > 0 ? `$${vi.estimatedSavings.toLocaleString()}` : "—"}
                        </td>
                      )}
                      <td className="px-4 py-4 text-left text-xs text-[#64748B]">{vi.countryOfOrigin || "—"}</td>
                      <td className="px-4 py-4 text-left text-[10px] text-slate-500">
                        {vi.dutyScenarios?.basis?.disclaimer || "MFN rate estimate"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!isPreCompliance && totalPotentialSavings > 0 && (
              <div className="px-4 py-3 border-t bg-green-50/50">
                <p className="text-sm font-semibold text-green-800">
                  Total potential savings: ${totalPotentialSavings.toLocaleString()}
                </p>
                <p className="text-[11px] text-green-700 mt-0.5">Review before export. Estimates only.</p>
              </div>
            )}
          </div>
        )
      })()}

      {/* ═══════════════════════════════════════════════════════════════════
          DOMAIN 3: REGULATORY (only shown when flags / alerts exist)
          ═══════════════════════════════════════════════════════════════════ */}
      {(regulatoryFlags.length > 0 || shipmentAlerts.length > 0) && (
        <div className="rounded-2xl border bg-card shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-amber-50/50">
            <h3 className="font-semibold text-amber-900">Regulatory Flags</h3>
            <p className="text-[11px] text-amber-800/80 mt-0.5">
              Regulatory screening is advisory only. Confirm all requirements with your compliance officer.
            </p>
          </div>
          <div className="px-4 py-3 space-y-3">
            {regulatoryFlags.length > 0 && (
              <div>
                <p className="text-sm font-medium text-amber-900 mb-1">Applicable flags</p>
                <ul className="text-sm text-amber-800 list-disc list-inside space-y-0.5">
                  {regulatoryFlags.slice(0, 8).map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                  {regulatoryFlags.length > 8 && (
                    <li className="text-amber-700 font-medium">+{regulatoryFlags.length - 8} more</li>
                  )}
                </ul>
              </div>
            )}
            {shipmentAlerts.length > 0 && (
              <div>
                <p className="text-sm font-medium text-amber-900 mb-1">Compliance alerts</p>
                <div className="flex flex-wrap gap-2">
                  {shipmentAlerts.slice(0, 5).map((a: any) => (
                    <span key={a.id} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-amber-50 border border-amber-200 text-xs">
                      <code>{a.hts_code || "—"}</code>
                      <span className="text-amber-800">{a.alert_type}</span>
                      {a.duty_delta_estimate && <span className="text-green-700">{a.duty_delta_estimate}</span>}
                    </span>
                  ))}
                </div>
                <Link href="/app/psc-radar" className="text-blue-600 text-xs hover:underline mt-2 inline-block">View all compliance alerts</Link>
              </div>
            )}
            <div className="flex flex-wrap gap-2 pt-2 border-t border-amber-100">
              {onSwitchToDocuments && (
                <Button size="sm" variant="outline" onClick={onSwitchToDocuments}>
                  Request data sheet in Documents
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  const note = `Broker note: Regulatory flags present for shipment ${shipmentId}. Please verify requirements before filing. Flags: ${regulatoryFlags.slice(0, 5).join("; ")}`
                  if (typeof navigator !== "undefined" && navigator.clipboard) {
                    void navigator.clipboard.writeText(note)
                  }
                }}
              >
                Copy note for broker
              </Button>
              {canOpenReviews && (
                <Button size="sm" onClick={handleOpenReviews}>Mark for broker review</Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. Why this applies — keep focused for entry compliance */}
      {!isPreCompliance && <div className="rounded-2xl border bg-card shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b">
          <h3 className="font-semibold">Why this applies</h3>
        </div>
        <div className="divide-y">
          {(() => {
            const withRec = viewItems.filter((i: any) => i.recommendedHts)
            const seen = new Map<string, number[]>()
            withRec.forEach((vi: any) => {
              const key = `${vi.declaredHts}|${vi.recommendedHts}|${vi.shortReason}`
              if (!seen.has(key)) seen.set(key, [])
              seen.get(key)!.push(vi.index)
            })
            return Array.from(seen.entries()).slice(0, 5).map(([key, indices], i) => {
              const vi = withRec.find((x: any) => x.index === indices[0])!
              const count = indices.length
              return (
                <div key={i} className="px-5 py-4">
                  <p className="text-sm line-clamp-2">
                    {count > 1 ? `${count} line items share the same classification issue. ` : ""}
                    This item was classified under HTS {vi.declaredHts}. {isPreCompliance ? "Likely HS code suggestion" : "Alternative"} {vi.recommendedHts} shows {vi.estimatedSavings > 0 ? "lower duty" : "different duty structure"} based on similar classifications and available documentation.
                  </p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {vi.evidenceSources?.map((s: string, j: number) => (
                      <span key={j} className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs" title={`Source: ${s}`}>{s}</span>
                    ))}
                  </div>
                </div>
              )
            })
          })()}
        </div>
      </div>}

      {/* 6. Collapsible advanced sections */}
      {!isPreCompliance && <details className="rounded-2xl border bg-card shadow-sm divide-y">
        <summary className="px-5 py-4 cursor-pointer hover:bg-muted/30 list-none flex items-center justify-between">
          <span className="font-medium">Advanced — Structural Analysis, Evidence, Audit Trail</span>
          <span className="text-muted-foreground text-sm">Click to expand</span>
        </summary>
        <div className="px-5 pb-5 space-y-4">
          <div>
            <p className="text-sm font-medium mb-1">What NECO evaluated</p>
            <ul className="text-sm text-muted-foreground space-y-1">
              {items.map((item: any, i: number) => (
                <li key={i}>
                  {item.label || `Item ${i + 1}`}: HTS <code className="text-xs">{item.hts_code || "—"}</code>
                  {item.classification?.primary_candidate && <> → {isPreCompliance ? "likely HS code" : "alternative"} <code className="text-xs">{item.classification.primary_candidate.hts_code}</code></>}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-sm font-medium mb-1">Out of scope</p>
            <ul className="text-sm text-muted-foreground list-disc list-inside space-y-0.5">
              {WHAT_WAS_NOT_EVALUATED.slice(0, 4).map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-sm font-medium mb-1">Documents used</p>
            {resultJson?.evidence_map?.extraction_errors?.length > 0 ? (
              <div className="space-y-2">
                <WarningBox
                  warnings={(resultJson?.evidence_map?.extraction_errors ?? []).map((e: any) => ({
                    message: typeof e === "string" ? e : (e.error || e.message || "Extraction error"),
                  }))}
                />
                <p className="text-sm text-muted-foreground">
                  Fix document types in the <strong>Documents</strong> tab, then Re-run to re-scan.
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {resultJson?.evidence_map?.documents?.map((d: any) => d.filename || d.document_type).join(", ") || "Entry Summary, Commercial Invoice"}
              </p>
            )}
          </div>
          <div>
            <p className="text-sm font-medium mb-1">Audit trail</p>
            <p className="text-sm text-muted-foreground">
              Shipment {resultJson?.shipment_id} · Generated {resultJson?.generated_at ? new Date(resultJson.generated_at).toLocaleString() : "—"}
            </p>
          </div>
          {blockers.length > 0 && (
            <div>
              <p className="text-sm font-medium text-amber-700 mb-1">Flags</p>
              <ul className="text-sm list-disc list-inside text-amber-800">
                {blockers.map((b: any, i: number) => (
                  <li key={i}>{typeof b === "string" ? b : b?.message}</li>
                ))}
              </ul>
            </div>
          )}
          {warnings.length > 0 && (
            <p className="text-sm text-muted-foreground">{warnings.length} warning(s) in this analysis.</p>
          )}
        </div>
      </details>}

      {/* HS Code Review — clarification answers + suggestions (visible when questions exist) */}
      {!isPreCompliance && items.some((i: any) => i.classification?.candidates?.length || i.classification?.questions?.length || i.classification?.review_explanation || i.clarification_questions?.length || i.psc?.alternatives?.length) && (
        <Card>
          <CardContent className="pt-6">
            <details className="group" open={hasClarificationQuestions}>
              <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground list-none flex items-center gap-2">
                <span className="group-open:rotate-90 transition-transform">▸</span>
                HS Code Review — {hasClarificationQuestions ? "Answer questions below, then Re-run" : isPreCompliance ? "likely HS code suggestions and clarification questions" : "alternative codes, risk %, and clarification questions"}
              </summary>
              <div className="mt-3 space-y-4 pl-4 border-l-2 border-border">
                {items.map((item: any, idx: number) => {
                  const cl = item.classification
                  const questions = cl?.questions || item.clarification_questions || []
                  const reviewExp = cl?.review_explanation
                  const candidates = cl?.candidates || []
                  const pscAlts = item.psc?.alternatives || []
                  const itemId = item.id || `item-${idx}`
                  if (!questions.length && !reviewExp && !candidates.length && !pscAlts.length) return null
                  return (
                    <div key={idx} className="text-sm space-y-2">
                      <p className="font-medium">{item.label || `Item ${idx + 1}`}</p>
                      {questions.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-amber-700 mb-0.5">Answer these to clarify classification:</p>
                          {questions.map((q: any, qi: number) => {
                            const attr = q.attribute || q.question?.slice(0, 30) || `q${qi}`
                            const val = clarificationAnswers[itemId]?.[attr] ?? ""
                            return (
                              <div key={qi} className="flex flex-wrap items-center gap-2">
                                <label className="text-muted-foreground min-w-[140px]">{q.question || q.attribute || attr}:</label>
                                <input
                                  type="text"
                                  value={val}
                                  onChange={(e) =>
                                    setClarificationAnswers((prev) => ({
                                      ...prev,
                                      [itemId]: { ...(prev[itemId] || {}), [attr]: e.target.value },
                                    }))
                                  }
                                  placeholder="Your answer"
                                  className="rounded-md border border-input bg-background px-3 py-1.5 text-sm max-w-[200px]"
                                />
                              </div>
                            )
                          })}
                        </div>
                      )}
                      {reviewExp?.primary_reasons?.length > 0 && (
                        <p className="text-muted-foreground">Why review: {reviewExp.primary_reasons.slice(0, 2).join("; ")}</p>
                      )}
                      {(candidates.length > 0 || pscAlts.length > 0) && (
                        <ul className="list-disc list-inside text-muted-foreground space-y-0.5">
                          {(pscAlts.length ? pscAlts : candidates).slice(0, 3).map((c: any, ci: number) => {
                            const hts = c.alternative_hts_code || c.hts_code
                            const rate = c.alternative_duty_rate || c.duty_rate_general
                            const sim = c.similarity_score != null ? Math.round((1 - c.similarity_score) * 100) : null
                            return (
                              <li key={ci}>
                                <code className="text-xs">{hts}</code>
                                {rate && ` (${rate})`}
                                {sim != null && ` ~${sim}% risk`}
                              </li>
                            )
                          })}
                        </ul>
                      )}
                    </div>
                  )
                })}
                {hasClarificationQuestions && onReRunWithClarifications && (
                  <div className="pt-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        const responses: Record<string, Record<string, string>> = {}
                        items.forEach((item: any, idx: number) => {
                          const itemId = item.id || `item-${idx}`
                          const answers = clarificationAnswers[itemId]
                          if (answers && Object.keys(answers).length > 0) {
                            responses[itemId] = answers
                          }
                        })
                        onReRunWithClarifications(responses)
                      }}
                      disabled={analyzing}
                    >
                      {analyzing ? "Re-running…" : "Re-run with answers"}
                    </Button>
                  </div>
                )}
              </div>
            </details>
          </CardContent>
        </Card>
      )}

      {/* Supplemental Evidence — entry compliance only to keep pre-compliance action-focused */}
      {!isPreCompliance && shipmentId && apiPost && apiPostForm && apiDelete && onRefresh && items.length > 0 && (() => {
        const displayItems = items.filter((item: any) => item.needs_supplemental_evidence || item.supplemental_evidence_source)
        if (displayItems.length === 0) return null
        return (
          <Card>
            <CardHeader>
              <CardTitle>Supplemental Evidence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Add Amazon URL, upload a PDF data sheet, or mark N/A if not available.
              </p>
              {displayItems.map((item: any, i: number) => (
                <div key={item.id || i} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{item.label || `Item ${i + 1}`}</p>
                    {item.needs_supplemental_evidence && !item.supplemental_evidence_source && (
                      <span className="text-xs text-amber-600 font-medium">Needs more data</span>
                    )}
                  </div>
                  {item.supplemental_evidence_source ? (
                    <p className="text-sm text-green-700">
                      ✓ {item.supplemental_evidence_source === "amazon_url" ? "Amazon" : "PDF"} added. Re-run to use it.
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2 items-center">
                    <input
                      type="url"
                      placeholder="Amazon URL (https://www.amazon.com/dp/...)"
                      value={supplementalUrl[item.id] ?? ""}
                      onChange={(e) => setSupplementalUrl((s) => ({ ...s, [item.id]: e.target.value }))}
                      className="flex-1 min-w-[180px] rounded border border-input bg-background px-2 py-1.5 text-sm"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={supplementalSubmitting[item.id] || !(supplementalUrl[item.id] ?? "").trim()}
                      onClick={async () => {
                        const url = (supplementalUrl[item.id] ?? "").trim()
                        if (!url || !apiPost) return
                        setSupplementalSubmitting((s) => ({ ...s, [item.id]: true }))
                        try {
                          await apiPost(`/api/v1/shipments/${shipmentId}/items/${item.id}/supplemental-evidence`, { type: "amazon_url", amazon_url: url })
                          setSupplementalUrl((s) => ({ ...s, [item.id]: "" }))
                          onRefresh()
                        } finally {
                          setSupplementalSubmitting((s) => ({ ...s, [item.id]: false }))
                        }
                      }}
                    >
                      {supplementalSubmitting[item.id] ? "Adding…" : "Amazon"}
                    </Button>
                    <label className="inline-flex items-center justify-center rounded-md text-sm font-medium border border-input bg-background px-3 py-1.5 hover:bg-accent cursor-pointer">
                      PDF
                      <input
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        onChange={async (e) => {
                            const f = e.target.files?.[0]
                            if (!f || !apiPostForm) return
                            setSupplementalSubmitting((s) => ({ ...s, [item.id]: true }))
                            try {
                              const formData = new FormData()
                              formData.append("file", f)
                              await apiPostForm(`/api/v1/shipments/${shipmentId}/items/${item.id}/supplemental-evidence/upload`, formData)
                              onRefresh()
                            } finally {
                              setSupplementalSubmitting((s) => ({ ...s, [item.id]: false }))
                              e.target.value = ""
                            }
                          }}
                        />
                    </label>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-muted-foreground"
                      disabled={supplementalSubmitting[item.id]}
                      onClick={async () => {
                        if (!apiDelete) return
                        setSupplementalSubmitting((s) => ({ ...s, [item.id]: true }))
                        try {
                          await apiDelete(`/api/v1/shipments/${shipmentId}/items/${item.id}/supplemental-evidence`)
                          onRefresh()
                        } finally {
                          setSupplementalSubmitting((s) => ({ ...s, [item.id]: false }))
                        }
                      }}
                    >
                      N/A
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )
      })()}

      {/* 7. Sticky footer action bar — primary: Review Items, secondary: Export */}
      <div className="sticky bottom-0 z-30 border-t bg-background/95 backdrop-blur px-6 py-4 -mx-6 -mb-6 flex justify-end gap-3">
        {canOpenReviews && (
          <Button onClick={handleOpenReviews}>{reviewRequiredCount > 0 ? `Review ${reviewRequiredCount} Items` : "Review Items"}</Button>
        )}
        {onSwitchToExports && (
          <Button variant="secondary" onClick={onSwitchToExports}>Export Summary to Broker</Button>
        )}
      </div>
    </div>
    </>
  )
}
