"use client"

import { useEffect, useState } from "react"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { useAuth, useOrganization } from "@clerk/nextjs"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Radar } from "lucide-react"

interface PSCAlertItem {
  id: string
  signal_id: string
  hts_code: string | null
  alert_type: string | null
  duty_delta_estimate: string | null
  reason: string | null
  status: string
  explanation: Record<string, unknown> | null
  evidence_links: unknown[] | null
  created_at: string | null
  source_url: string | null
  source_title: string | null
  shipment_id: string | null
  confidence_score: number | null
  priority: string | null
  signal_source: string | null
  fill_rate_pct?: number
}

export default function PSCRadarPage() {
  const router = useRouter()
  const { apiGet, apiPatch, effectiveOrgId, useDevAuth } = useApiClient()
  const { isLoaded: authLoaded } = useAuth()
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const resolvedOrgId =
    effectiveOrgId ||
    organization?.id ||
    process.env.NEXT_PUBLIC_TEST_ORG_ID ||
    null

  const [alerts, setAlerts] = useState<PSCAlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>("")
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  useEffect(() => {
    if (!useDevAuth && (!authLoaded || !orgLoaded)) {
      return
    }
    if (!resolvedOrgId) {
      if (!useDevAuth) router.replace("/app/organizations/select")
      return
    }

    let cancelled = false

    const loadAlerts = async () => {
      try {
        const params = new URLSearchParams()
        if (statusFilter) params.set("status", statusFilter)
        const data = await apiGet<{ items: PSCAlertItem[]; count: number }>(
          `/api/v1/psc-radar/alerts?${params.toString()}`
        )
        if (!cancelled) {
          setAlerts(data.items || [])
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(formatApiError(e as ApiClientError))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadAlerts()
    return () => {
      cancelled = true
    }
  }, [apiGet, authLoaded, orgLoaded, resolvedOrgId, useDevAuth, router, statusFilter])

  const handleStatusUpdate = async (alertId: string, newStatus: "reviewed" | "dismissed") => {
    setUpdatingId(alertId)
    setError(null)
    try {
      await apiPatch(`/api/v1/psc-radar/alerts/${alertId}`, { status: newStatus })
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: newStatus } : a
        )
      )
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Radar className="h-8 w-8" />
          PSC Radar
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Compliance Alerts</CardTitle>
          <p className="text-sm text-muted-foreground">
            Regulatory signals that may affect your shipments. No filing recommendation is made. This analysis is for informational purposes only.
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <Button
              variant={statusFilter === "" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("")}
            >
              All
            </Button>
            <Button
              variant={statusFilter === "new" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("new")}
            >
              New
            </Button>
            <Button
              variant={statusFilter === "reviewed" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("reviewed")}
            >
              Reviewed
            </Button>
            <Button
              variant={statusFilter === "dismissed" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("dismissed")}
            >
              Dismissed
            </Button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="border rounded-lg">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">HTS</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Signal</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Duty Delta</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Fill %</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Priority</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Created</th>
                  <th className="px-4 py-3 text-right text-sm font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      Loading alerts...
                    </td>
                  </tr>
                ) : alerts.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No PSC alerts. Regulatory signals will appear here when they match your organization&apos;s HTS usage.
                    </td>
                  </tr>
                ) : (
                  alerts.map((a) => (
                    <tr key={a.id} className="border-t">
                      <td className="px-4 py-3 text-sm font-mono">{a.hts_code || "—"}</td>
                      <td className="px-4 py-3 text-sm">
                        <div>
                          {a.source_title && (
                            <span className="font-medium">{a.source_title}</span>
                          )}
                          {a.reason && (
                            <p className="text-muted-foreground text-xs mt-1 line-clamp-2">{a.reason}</p>
                          )}
                          {a.source_url && (
                            <a
                              href={a.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 text-xs hover:underline"
                            >
                              Source
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm">{a.duty_delta_estimate || "—"}</td>
                      <td className="px-4 py-3 text-sm">{a.fill_rate_pct != null ? `${a.fill_rate_pct}%` : "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded text-xs ${
                          a.priority === "HIGH" ? "bg-red-100 text-red-800" :
                          a.priority === "MEDIUM" ? "bg-amber-100 text-amber-800" : "bg-gray-100"
                        }`}>
                          {a.priority || "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                            a.status === "new"
                              ? "bg-amber-100 text-amber-800"
                              : a.status === "reviewed"
                              ? "bg-green-100 text-green-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {a.created_at
                          ? new Date(a.created_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {a.status === "new" && (
                          <div className="flex gap-2 justify-end">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleStatusUpdate(a.id, "reviewed")}
                              disabled={updatingId === a.id}
                            >
                              Review
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleStatusUpdate(a.id, "dismissed")}
                              disabled={updatingId === a.id}
                            >
                              Dismiss
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
