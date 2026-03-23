/**
 * Reviews Tab - Sprint 15
 *
 * Review status, accept/reject with notes, override with audit warning, history.
 * Shows items to review (from analysis) with Declared HTS, Recommended HTS, reason.
 */

"use client"

import { Fragment, useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusPill } from "@/components/ui/status-pill"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"

interface ReviewListItem {
  id: string
  status: string
  created_at: string
  reviewed_at?: string | null
  reviewed_by?: string | null
  review_notes?: string | null
  prior_review_id?: string | null
}

interface ReviewDetail {
  id: string
  object_type: string
  status: string
  review_reason_code?: string | null
  created_at: string
  created_by: string
  prior_review_id?: string | null
  snapshot_json: Record<string, any>
  regulatory_evaluations: Array<{
    id: string
    regulator: string
    outcome: string
    explanation_text: string
  }>
}

const REVIEW_REQUIRED = "REVIEW_REQUIRED"

function _regulatoryGuidance(regulator: string): string {
  const key = String(regulator || "").toUpperCase()
  if (key.includes("FDA")) {
    return "What it means: product category may require FDA review. What NECO needs: product specs or intended use details. What to share with broker/importer: product data sheet and product URL."
  }
  if (key.includes("LACEY")) {
    return "What it means: Lacey Act materials disclosure may be required. What NECO needs: material composition and species/origin details. What to share with broker/importer: supplier declaration and supporting product documentation."
  }
  if (key.includes("EPA")) {
    return "What it means: product may require EPA compliance verification. What NECO needs: model details and applicable compliance documents. What to share with broker/importer: product specifications and certifications."
  }
  return "What it means: this line may need additional compliance verification. What NECO needs: clearer product and origin details. What to share with broker/importer: relevant product documentation."
}

function _reframeReason(raw: string | undefined, altHts: string | undefined): string {
  const s = (raw || "").trim()
  if (
    altHts &&
    /no alternative|no plausible classifications|no good match|no confident match/i.test(s)
  ) {
    return "Alternative HTS identified from available document evidence. Review before export."
  }
  if (/could not resolve|couldn't resolve|unable to resolve|failed to resolve/i.test(s)) {
    return altHts
      ? "Declared HTS lacks complete duty resolution. Alternative shows defined duty and potential savings."
      : "Declared HTS lacks complete duty resolution. Review recommended."
  }
  if (s && s.length <= 120) return s
  if (s) return s.slice(0, 117) + "…"
  return altHts ? "Alternative HTS identified for review." : "Review recommended."
}

export function ReviewsTab({ shipment, shipmentId }: { shipment: any; shipmentId: string }) {
  const { apiGet, apiPost, apiPatch } = useApiClient()
  const [reviews, setReviews] = useState<ReviewListItem[]>([])
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null)
  const [reviewDetail, setReviewDetail] = useState<ReviewDetail | null>(null)
  const [analysisData, setAnalysisData] = useState<{ result_json?: any } | null>(null)
  const [overrideJustification, setOverrideJustification] = useState("")
  const [rejectNotes, setRejectNotes] = useState("")
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedItemIndex, setExpandedItemIndex] = useState<number | null>(null)
  const [lineDecisions, setLineDecisions] = useState<Record<number, "accept" | "override" | "leave">>({})

  const loadAnalysisStatus = useCallback(async () => {
    try {
      const status = await apiGet<any>(`/api/v1/shipments/${shipmentId}/analysis-status`)
      setAnalysisData(status)
    } catch (e: unknown) {
      if ((e as { status?: number })?.status !== 404) {
        setAnalysisData(null)
      }
    }
  }, [apiGet, shipmentId])

  const loadReviews = async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await apiGet<ReviewListItem[]>(
        `/api/v1/reviews/shipments/${shipmentId}/reviews`
      )
      setReviews(list)
      const nextSelected = selectedReviewId && list.some((r) => r.id === selectedReviewId)
        ? selectedReviewId
        : list[0]?.id || null
      setSelectedReviewId(nextSelected)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to load reviews")
    } finally {
      setLoading(false)
    }
  }

  const loadReviewDetail = async (reviewId: string) => {
    setError(null)
    try {
      const detail = await apiGet<ReviewDetail>(`/api/v1/reviews/${reviewId}`)
      setReviewDetail(detail)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to load review detail")
      setReviewDetail(null)
    }
  }

  useEffect(() => {
    loadReviews()
    loadAnalysisStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipmentId])

  useEffect(() => {
    if (!selectedReviewId) {
      setReviewDetail(null)
      return
    }
    loadReviewDetail(selectedReviewId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedReviewId])

  const handleAccept = async () => {
    if (!selectedReviewId) return
    setSubmitting(true)
    setError(null)
    try {
      await apiPatch(`/api/v1/reviews/${selectedReviewId}`, { action: "accept" })
      await loadReviews()
      await loadAnalysisStatus()
      if (selectedReviewId) await loadReviewDetail(selectedReviewId)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to accept")
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    if (!selectedReviewId || !rejectNotes.trim()) {
      setError("Notes are required when rejecting.")
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await apiPatch(`/api/v1/reviews/${selectedReviewId}`, {
        action: "reject",
        notes: rejectNotes.trim(),
      })
      setRejectNotes("")
      setShowRejectModal(false)
      await loadReviews()
      await loadAnalysisStatus()
      if (selectedReviewId) await loadReviewDetail(selectedReviewId)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to reject")
    } finally {
      setSubmitting(false)
    }
  }

  const handleCreateOverride = async () => {
    if (!selectedReviewId) return
    if (overrideJustification.trim().length < 10) {
      setError("Override justification must be at least 10 characters.")
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await apiPost(`/api/v1/reviews/${selectedReviewId}/override`, {
        justification: overrideJustification.trim(),
      })
      setOverrideJustification("")
      await loadReviews()
      await loadAnalysisStatus()
      const newFirst = (await apiGet<ReviewListItem[]>(`/api/v1/reviews/shipments/${shipmentId}/reviews`))[0]
      if (newFirst) setSelectedReviewId(newFirst.id)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to create override")
    } finally {
      setSubmitting(false)
    }
  }

  const canAcceptReject = reviewDetail?.status === REVIEW_REQUIRED

  // Build items to review from analysis data (same view model as Analysis tab)
  const items = analysisData?.result_json?.items || []
  const blockers = analysisData?.result_json?.blockers || []
  const viewItems = items.map((item: any, idx: number) => {
    const pscAlts = item.psc?.alternatives || []
    const candidates = item.classification?.candidates || []
    const primary = item.classification?.primary_candidate
    const bestAlt = pscAlts[0] || primary || candidates[0]
    const altHts = bestAlt?.alternative_hts_code || bestAlt?.hts_code
    const duty = item.duty
    const dutyFromEs = item.duty_from_entry_summary
    const customsValue = typeof item.value === "number" ? item.value : parseFloat(item.value) || 0
    const altRate = bestAlt?.alternative_duty_rate || bestAlt?.duty_rate_general
    const altRateNum = altRate ? parseFloat(String(altRate).replace("%", "")) / 100 : null
    const declaredRate = duty?.resolved_general_raw ? parseFloat(String(duty.resolved_general_raw).replace("%", "")) / 100 : null
    const deltaAmount = pscAlts[0]?.delta_amount ?? (altRateNum != null && declaredRate != null && customsValue > 0 ? (declaredRate - altRateNum) * customsValue : null)
    const altEst = customsValue > 0 && altRateNum != null ? altRateNum * customsValue : (pscAlts[0]?.delta_amount ?? null)
    const estimatedSavings = deltaAmount != null && deltaAmount > 0 ? deltaAmount : (altEst != null ? altEst : 0)
    return {
      index: idx,
      productName: item.label || `Item ${idx + 1}`,
      declaredHts: item.hts_code || "—",
      recommendedHts: altHts,
      estimatedSavings,
      shortReason: _reframeReason(item.psc?.summary, altHts),
      confidence: item.classification?.metadata?.analysis_confidence ?? 0.6,
      risk: blockers.length > 0 ? "Medium" : "Low",
    }
  }).filter((vi: any) => vi.recommendedHts || vi.estimatedSavings > 0)

  const totalSavings = viewItems.reduce((s: number, i: any) => s + (i.estimatedSavings || 0), 0)
  const safeItems = viewItems.filter((i: any) => i.risk !== "Medium")

  useEffect(() => {
    if (typeof window === "undefined") return
    const raw = window.sessionStorage.getItem("neco_reviews_focus")
    if (!raw) return
    try {
      const parsed = JSON.parse(raw) as { index?: number }
      if (typeof parsed?.index === "number") setExpandedItemIndex(parsed.index)
    } catch {
      // ignore
    } finally {
      window.sessionStorage.removeItem("neco_reviews_focus")
    }
  }, [shipmentId])

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Review Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading reviews...</p>
          ) : reviews.length === 0 ? (
            <p className="text-sm text-muted-foreground">No review record. Run analysis to create one.</p>
          ) : reviewDetail ? (
            <>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Current status:</span>
                <StatusPill status={reviewDetail.status} />
              </div>
              {reviewDetail.status === REVIEW_REQUIRED && (
                <p className="text-sm text-amber-800">Export is blocked until review is complete.</p>
              )}

              {canAcceptReject && (
                <div className="flex gap-3 pt-2">
                  <Button onClick={handleAccept} disabled={submitting}>
                    {submitting ? "Accepting..." : "Accept classification"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setShowRejectModal(true)}
                    disabled={submitting}
                  >
                    Reject – needs verification
                  </Button>
                </div>
              )}

              {showRejectModal && (
                <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 space-y-3">
                  <p className="text-sm font-medium">Reject – provide notes (required)</p>
                  <textarea
                    value={rejectNotes}
                    onChange={(e) => setRejectNotes(e.target.value)}
                    placeholder="e.g. Needs verification with broker before accepting classification"
                    className="w-full min-h-20 rounded-md border p-2 text-sm"
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={handleReject}
                      disabled={!rejectNotes.trim() || submitting}
                    >
                      {submitting ? "Rejecting..." : "Reject"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setShowRejectModal(false)
                        setRejectNotes("")
                      }}
                      disabled={submitting}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Select a review below.</p>
          )}
        </CardContent>
      </Card>

      {/* Items to review — from analysis, consumable table */}
      {canAcceptReject && viewItems.length === 0 && items.length === 0 && analysisData === null && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">No analysis data. Go to the <strong>Analysis</strong> tab to run analysis and see items to review.</p>
          </CardContent>
        </Card>
      )}
      {canAcceptReject && viewItems.length === 0 && items.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">No alternative classifications identified. Declared HTS appears consistent. You can Accept to clear the review.</p>
          </CardContent>
        </Card>
      )}
      {viewItems.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Items to Review ({viewItems.length})</CardTitle>
            <p className="text-sm text-muted-foreground">
              {totalSavings > 0 ? `Potential savings: $${totalSavings.toLocaleString()}. ` : ""}
              Review each flagged line below before accepting or rejecting this shipment.
            </p>
            {safeItems.length > 0 && (
              <div className="pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const updates: Record<number, "accept" | "override" | "leave"> = {}
                    safeItems.forEach((item: any) => { updates[item.index] = "accept" })
                    setLineDecisions((prev) => ({ ...prev, ...updates }))
                  }}
                >
                  Accept all safe items
                </Button>
              </div>
            )}
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Item</th>
                    <th className="px-4 py-2 text-left font-medium">Declared HTS</th>
                    <th className="px-4 py-2 text-left font-medium">Alternative HTS identified</th>
                    <th className="px-4 py-2 text-right font-medium">Est. Savings</th>
                    <th className="px-4 py-2 text-left font-medium">Why this was flagged</th>
                  </tr>
                </thead>
                <tbody>
                  {viewItems.map((vi: any) => (
                    <Fragment key={vi.index}>
                    <tr
                      className="border-t hover:bg-muted/30 cursor-pointer"
                      onClick={() => setExpandedItemIndex((curr) => (curr === vi.index ? null : vi.index))}
                    >
                      <td className="px-4 py-3 font-medium">{vi.productName}</td>
                      <td className="px-4 py-3 font-mono text-xs">{vi.declaredHts}</td>
                      <td className="px-4 py-3 font-mono text-xs font-medium">{vi.recommendedHts || "—"}</td>
                      <td className="px-4 py-3 text-right font-semibold">{vi.estimatedSavings > 0 ? `$${vi.estimatedSavings.toLocaleString()}` : "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground max-w-[280px]">{vi.shortReason}</td>
                    </tr>
                    {expandedItemIndex === vi.index && (
                      <tr className="border-t bg-muted/20">
                        <td colSpan={5} className="px-4 py-3">
                          <div className="space-y-2 text-sm">
                            <p><strong>Why NECO surfaced this:</strong> {vi.shortReason}</p>
                            <p><strong>Evidence strength:</strong> {vi.confidence >= 0.7 ? "High" : vi.confidence >= 0.5 ? "Moderate" : "Low"}</p>
                            <p><strong>Review level:</strong> {vi.risk}</p>
                            <div className="flex flex-wrap gap-2 pt-1">
                              <Button
                                size="sm"
                                variant={lineDecisions[vi.index] === "accept" ? "default" : "outline"}
                                onClick={() => setLineDecisions((prev) => ({ ...prev, [vi.index]: "accept" }))}
                              >
                                Accept this line
                              </Button>
                              <Button
                                size="sm"
                                variant={lineDecisions[vi.index] === "override" ? "default" : "outline"}
                                onClick={() => setLineDecisions((prev) => ({ ...prev, [vi.index]: "override" }))}
                              >
                                Override this line
                              </Button>
                              <Button
                                size="sm"
                                variant={lineDecisions[vi.index] === "leave" ? "default" : "outline"}
                                onClick={() => setLineDecisions((prev) => ({ ...prev, [vi.index]: "leave" }))}
                              >
                                Leave this line
                              </Button>
                            </div>
                            {lineDecisions[vi.index] && (
                              <p className="text-xs text-[#334155]">
                                Selected action: <strong>{lineDecisions[vi.index]}</strong>. This is saved for this review session and can be changed anytime.
                              </p>
                            )}
                            <p className="text-muted-foreground">
                              Informational only: use this context to decide whether to accept, reject, or escalate to your broker.
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            {reviewDetail?.regulatory_evaluations && reviewDetail.regulatory_evaluations.length > 0 && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50/80 px-4 py-3">
                <p className="text-sm font-medium text-amber-900">Regulatory flags</p>
                <ul className="text-sm text-amber-800 mt-1 space-y-1">
                  {reviewDetail.regulatory_evaluations.map((r: any) => (
                    <li key={r.id}>
                      <strong>{r.regulator}</strong>: {r.explanation_text || r.outcome}
                      <div className="text-xs mt-1">{_regulatoryGuidance(r.regulator)}</div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Review History</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : reviews.length === 0 ? (
            <p className="text-sm text-muted-foreground">No reviews yet.</p>
          ) : (
            <div className="space-y-2">
              {reviews.map((review) => (
                <button
                  key={review.id}
                  type="button"
                  onClick={() => setSelectedReviewId(review.id)}
                  className={`w-full text-left rounded-lg border p-3 ${
                    selectedReviewId === review.id ? "border-blue-400 bg-blue-50" : "border-border"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-medium text-sm">{review.status.replace(/_/g, " ")}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(review.created_at).toLocaleString()}
                        {review.reviewed_at && ` · Reviewed ${new Date(review.reviewed_at).toLocaleDateString()}`}
                        {review.prior_review_id && " · Override"}
                      </p>
                    </div>
                    <StatusPill status={review.status} />
                  </div>
                  {review.review_notes && (
                    <p className="mt-2 text-xs text-muted-foreground italic border-t pt-2">{review.review_notes}</p>
                  )}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Override Classification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-sm text-amber-900">
            This action will be logged and auditable. Use only when you have justification to override the system classification.
          </div>
          <textarea
            value={overrideJustification}
            onChange={(e) => setOverrideJustification(e.target.value)}
            placeholder="Provide justification for override (required, min 10 characters)"
            className="w-full min-h-24 rounded-md border p-2 text-sm"
          />
          <Button
            type="button"
            variant="outline"
            disabled={!selectedReviewId || submitting || overrideJustification.trim().length < 10}
            onClick={handleCreateOverride}
          >
            {submitting ? "Creating..." : "Override Classification"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
