/**
 * Exports Tab - Sprint 12
 *
 * Generate and download exports.
 */

"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusPill } from "@/components/ui/status-pill"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"

interface ReviewListItem {
  id: string
  status: string
  created_at: string
}

interface ExportResponse {
  id: string
  review_id: string
  export_type: string
  status: string
  created_at: string
  completed_at?: string
  blocked_reason?: string
  blockers?: string[]
  error_message?: string
}

const REVIEW_REQUIRED = "REVIEW_REQUIRED"

interface ExportsTabProps {
  shipment: any
  shipmentId: string
  onSwitchToReviews?: () => void
}

export function ExportsTab({ shipment, shipmentId, onSwitchToReviews }: ExportsTabProps) {
  const { apiGet, apiPost, apiGetBlob } = useApiClient()
  const [reviews, setReviews] = useState<ReviewListItem[]>([])
  const [selectedReviewId, setSelectedReviewId] = useState<string>("")
  const [latestExport, setLatestExport] = useState<ExportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedReview = selectedReviewId
    ? reviews.find((r) => r.id === selectedReviewId)
    : null
  const isExportBlocked = selectedReview?.status === REVIEW_REQUIRED

  const loadReviews = async () => {
    setLoading(true)
    setError(null)
    try {
      const reviewList = await apiGet<ReviewListItem[]>(
        `/api/v1/reviews/shipments/${shipmentId}/reviews`
      )
      setReviews(reviewList)
      if (!selectedReviewId && reviewList[0]) {
        setSelectedReviewId(reviewList[0].id)
      }
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to load reviews for export")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReviews()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipmentId])

  const createExport = async (kind: "audit-pack" | "broker-prep") => {
    if (!selectedReviewId) {
      setError("Select a review before generating export.")
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const exportResult = await apiPost<ExportResponse>(
        `/api/v1/reviews/${selectedReviewId}/exports/${kind}`
      )
      setLatestExport(exportResult)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to generate export")
    } finally {
      setSubmitting(false)
    }
  }

  const refreshExportStatus = async () => {
    if (!latestExport?.id) {
      return
    }
    try {
      const status = await apiGet<ExportResponse>(`/api/v1/exports/${latestExport.id}/status`)
      setLatestExport(status)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to refresh export status")
    }
  }

  const openDownload = async () => {
    if (!latestExport?.id) return
    setError(null)
    try {
      const payload = await apiGet<{ download_url: string }>(
        `/api/v1/exports/${latestExport.id}/download-url`
      )
      const url = payload.download_url
      // Local backend stream: use auth and blob download (no presigned S3 URL)
      if (url.includes("/api/v1/exports/") && url.includes("/download")) {
        const path = new URL(url).pathname
        const blob = await apiGetBlob(path)
        const objectUrl = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = objectUrl
        a.download = `filing-prep-${latestExport.id}.zip`
        a.click()
        URL.revokeObjectURL(objectUrl)
      } else {
        window.open(url, "_blank")
      }
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to get export download URL")
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
          <p className="text-sm text-amber-800">{error}</p>
          <p className="text-sm text-amber-800">
            If export is blocked, complete the review in the <strong>Reviews</strong> tab and try again. For download issues, check your connection and retry.
          </p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Generate Export</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading review records...</p>
          ) : reviews.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No reviews available. Run analysis to generate a review first.
            </p>
          ) : (
            <>
              {isExportBlocked && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 space-y-2">
                  <p className="font-medium">Export is blocked until review is complete.</p>
                  <p>
                    This review has status <strong>REVIEW_REQUIRED</strong>. Resolve accept/reject in the Reviews tab, then return here to generate or download filing-prep.
                  </p>
                  {onSwitchToReviews && (
                    <Button size="sm" variant="outline" onClick={onSwitchToReviews} className="mt-2">
                      Go to Reviews tab
                    </Button>
                  )}
                </div>
              )}
              <div>
                <label htmlFor="review-id" className="text-sm font-medium">
                  Review Record
                </label>
                <select
                  id="review-id"
                  value={selectedReviewId}
                  onChange={(e) => setSelectedReviewId(e.target.value)}
                  className="mt-1 w-full rounded-md border px-3 py-2 bg-background"
                >
                  {reviews.map((review) => (
                    <option key={review.id} value={review.id}>
                      {review.id} ({review.status})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3">
                <Button
                  type="button"
                  disabled={submitting || !selectedReviewId || isExportBlocked}
                  onClick={() => createExport("broker-prep")}
                >
                  {submitting ? "Generating..." : "Download filing-prep"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={submitting || !selectedReviewId}
                  onClick={() => createExport("audit-pack")}
                >
                  {submitting ? "Generating..." : "Generate Audit Pack"}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Latest Export</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!latestExport ? (
            <p className="text-sm text-muted-foreground">No export generated in this session yet.</p>
          ) : (
            <>
              <div className="text-sm space-y-1">
                <p><strong>ID:</strong> <code className="text-xs">{latestExport.id}</code></p>
                <p><strong>Type:</strong> {latestExport.export_type}</p>
                <p className="flex items-center gap-2">
                  <strong>Status:</strong> <StatusPill status={latestExport.status} />
                </p>
                {latestExport.blocked_reason && (
                  <p className="text-orange-700"><strong>Blocked:</strong> {latestExport.blocked_reason}</p>
                )}
                {latestExport.error_message && (
                  <div className="text-amber-800 space-y-1">
                    <p><strong>Export issue:</strong> {latestExport.error_message}</p>
                    <p className="text-sm">Complete the review in the Reviews tab if required, then generate again.</p>
                  </div>
                )}
              </div>
              <div className="flex gap-3">
                <Button type="button" variant="outline" onClick={refreshExportStatus}>
                  Refresh Status
                </Button>
                <Button
                  type="button"
                  onClick={openDownload}
                  disabled={latestExport.status !== "COMPLETED"}
                >
                  Download
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
