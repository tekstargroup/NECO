"use client"

import { useCallback, useEffect, useState } from "react"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { useAuth, useOrganization } from "@clerk/nextjs"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Activity, CheckCircle2, AlertTriangle, XCircle, RefreshCw, Rss, FlaskConical } from "lucide-react"

interface SourceStatus {
  name: string
  type: string
  tier: number
  frequency: string
  count: number
  last_ingested_at: string | null
  status: "ok" | "stale" | "no_data"
}

interface SignalHealthResponse {
  overall: "ok" | "warning" | "critical"
  generated_at: string
  summary: {
    sources_ok: number
    sources_stale: number
    sources_no_data: number
    sources_total: number
    raw_signals_total: number
    normalized_signals_total: number
    alerts_total: number
    alerts_last_24h: number
    alerts_last_7d: number
  }
  sources: SourceStatus[]
  celery_schedule: Record<string, string>
}

interface TestSourceResult {
  name: string
  type: string
  tier: number
  status: "ok" | "empty" | "fail" | "skipped"
  items_count: number
  error?: string
}

interface TestSourcesResponse {
  summary: { ok: number; empty: number; fail: number; skipped: number; total: number }
  sources: TestSourceResult[]
}

export default function SignalHealthPage() {
  const router = useRouter()
  const { apiGet, apiPost, effectiveOrgId, useDevAuth } = useApiClient()
  const { isLoaded: authLoaded } = useAuth()
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const resolvedOrgId =
    effectiveOrgId ||
    organization?.id ||
    process.env.NEXT_PUBLIC_TEST_ORG_ID ||
    null

  const [data, setData] = useState<SignalHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<TestSourcesResponse | null>(null)
  const [testing, setTesting] = useState(false)
  const [polling, setPolling] = useState(false)

  const loadHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiGet<SignalHealthResponse>("/api/v1/compliance/signal-health")
      setData(res)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setLoading(false)
    }
  }, [apiGet])

  const runTestAllSources = useCallback(async () => {
    setTesting(true)
    setError(null)
    setTestResults(null)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 120_000)
    try {
      // Test can take 30-90s; use 2-min timeout
      const res = await apiGet<TestSourcesResponse>("/api/v1/compliance/test-sources", {
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      setTestResults(res)
    } catch (e: unknown) {
      clearTimeout(timeoutId)
      const err = e as ApiClientError & { name?: string }
      if (err?.name === "AbortError") {
        setError("Test timed out after 2 minutes. Some sources may be slow or unreachable.")
      } else {
        setError(formatApiError(e as ApiClientError))
      }
    } finally {
      setTesting(false)
    }
  }, [apiGet])

  const runPollNow = useCallback(async () => {
    setPolling(true)
    setError(null)
    try {
      await apiPost<{ status: string; inserted: Record<string, number> }>(
        "/api/v1/regulatory-updates/poll"
      )
      await loadHealth()
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setPolling(false)
    }
  }, [apiPost, loadHealth])

  const [processing, setProcessing] = useState(false)
  const [refreshingHts, setRefreshingHts] = useState(false)

  const runProcessNow = useCallback(async () => {
    setProcessing(true)
    setError(null)
    try {
      await apiPost<{ status: string }>("/api/v1/regulatory-updates/process")
      await loadHealth()
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setProcessing(false)
    }
  }, [apiPost, loadHealth])

  const runRefreshHts = useCallback(async () => {
    setRefreshingHts(true)
    setError(null)
    try {
      await apiPost<{ status: string }>("/api/v1/regulatory-updates/refresh-hts-usage")
      await loadHealth()
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError))
    } finally {
      setRefreshingHts(false)
    }
  }, [apiPost, loadHealth])

  useEffect(() => {
    if (!useDevAuth && (!authLoaded || !orgLoaded)) return
    loadHealth()
  }, [authLoaded, orgLoaded, useDevAuth, loadHealth])

  if (!useDevAuth && !resolvedOrgId) {
    router.replace("/app/organizations/select")
    return null
  }

  const OverallIcon =
    data?.overall === "ok"
      ? CheckCircle2
      : data?.overall === "warning"
      ? AlertTriangle
      : XCircle
  const overallColor =
    data?.overall === "ok"
      ? "text-green-600"
      : data?.overall === "warning"
      ? "text-amber-600"
      : "text-red-600"

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Activity className="h-8 w-8" />
          Signal Health
        </h1>
        <div className="flex gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={runTestAllSources}
            disabled={testing}
            title="Fetches from all 25 sources in parallel. May take 30–90 seconds."
          >
            <FlaskConical className={`h-4 w-4 mr-2 ${testing ? "animate-pulse" : ""}`} />
            {testing ? "Testing (30–90s)…" : "Test all sources"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={runPollNow}
            disabled={polling}
            title="Fetch from all sources and insert into DB. Populates raw_signals."
          >
            {polling ? "Polling…" : "Poll now"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={runProcessNow}
            disabled={processing}
            title="Process raw signals: normalize, classify, score, create alerts."
          >
            {processing ? "Processing…" : "Process now"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={runRefreshHts}
            disabled={refreshingHts}
            title="Refresh importer HTS usage from shipment data for relevance scoring."
          >
            {refreshingHts ? "Refreshing…" : "Refresh HTS"}
          </Button>
          <Button variant="outline" size="sm" onClick={loadHealth} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <p className="text-muted-foreground">
        Manager dashboard: ensure regulatory feeds are polling, signals are processing, and alerts are populating.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {loading && !data ? (
        <div className="text-center py-12 text-muted-foreground">Loading...</div>
      ) : data ? (
        <>
          {/* Overall status */}
          <Card className={data.overall === "critical" ? "border-red-300" : data.overall === "warning" ? "border-amber-300" : ""}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <OverallIcon className={`h-6 w-6 ${overallColor}`} />
                Overall: {data.overall.toUpperCase()}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Last updated: {new Date(data.generated_at).toLocaleString()}
              </p>
            </CardHeader>
          </Card>

          {/* Pipeline summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Raw Signals</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{data.summary.raw_signals_total.toLocaleString()}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Normalized</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{data.summary.normalized_signals_total.toLocaleString()}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Alerts (24h)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{data.summary.alerts_last_24h.toLocaleString()}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Alerts (7d)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{data.summary.alerts_last_7d.toLocaleString()}</p>
              </CardContent>
            </Card>
          </div>

          {/* Source status */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Rss className="h-5 w-5" />
                Feed Status ({data.summary.sources_ok} OK, {data.summary.sources_stale} stale, {data.summary.sources_no_data} no data)
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Celery Beat: poll every 5m/15m/1h/6h/1d; process signals hourly; refresh HTS usage daily.
              </p>
            </CardHeader>
            <CardContent>
              <div className="border rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">Source</th>
                      <th className="px-4 py-2 text-left font-medium">Type</th>
                      <th className="px-4 py-2 text-left font-medium">Tier</th>
                      <th className="px-4 py-2 text-left font-medium">Freq</th>
                      <th className="px-4 py-2 text-right font-medium">Count</th>
                      <th className="px-4 py-2 text-left font-medium">Last Ingested</th>
                      <th className="px-4 py-2 text-left font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sources.map((s) => (
                      <tr key={s.name} className="border-t">
                        <td className="px-4 py-2 font-mono">{s.name}</td>
                        <td className="px-4 py-2">{s.type}</td>
                        <td className="px-4 py-2">{s.tier}</td>
                        <td className="px-4 py-2">{s.frequency}</td>
                        <td className="px-4 py-2 text-right">{s.count.toLocaleString()}</td>
                        <td className="px-4 py-2 text-muted-foreground">
                          {s.last_ingested_at
                            ? new Date(s.last_ingested_at).toLocaleString()
                            : "—"}
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                              s.status === "ok"
                                ? "bg-green-100 text-green-800"
                                : s.status === "stale"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-gray-100 text-gray-600"
                            }`}
                          >
                            {s.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Test all sources */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="h-5 w-5" />
                Test all sources (Sprint 20 validation)
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Fetches from each RSS/API/scrape source without inserting. Validates feeds before proceeding.
                ok = items fetched; empty = 0 items (feed may be down or URL wrong); fail = error.
              </p>
            </CardHeader>
            <CardContent>
              {testResults ? (
                <>
                  <div className="flex gap-4 mb-4 text-sm">
                    <span className="text-green-600 font-medium">{testResults.summary.ok} OK</span>
                    <span className="text-amber-600">{testResults.summary.empty} empty</span>
                    <span className="text-red-600">{testResults.summary.fail} fail</span>
                    <span className="text-gray-500">{testResults.summary.skipped} skipped</span>
                  </div>
                  <div className="border rounded-lg overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted">
                        <tr>
                          <th className="px-4 py-2 text-left font-medium">Source</th>
                          <th className="px-4 py-2 text-left font-medium">Type</th>
                          <th className="px-4 py-2 text-left font-medium">Tier</th>
                          <th className="px-4 py-2 text-right font-medium">Items</th>
                          <th className="px-4 py-2 text-left font-medium">Status</th>
                          <th className="px-4 py-2 text-left font-medium">Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {testResults.sources.map((s) => (
                          <tr key={s.name} className="border-t">
                            <td className="px-4 py-2 font-mono">{s.name}</td>
                            <td className="px-4 py-2">{s.type}</td>
                            <td className="px-4 py-2">{s.tier}</td>
                            <td className="px-4 py-2 text-right">{s.items_count}</td>
                            <td className="px-4 py-2">
                              <span
                                className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                                  s.status === "ok"
                                    ? "bg-green-100 text-green-800"
                                    : s.status === "empty"
                                    ? "bg-amber-100 text-amber-800"
                                    : s.status === "fail"
                                    ? "bg-red-100 text-red-800"
                                    : "bg-gray-100 text-gray-600"
                                }`}
                              >
                                {s.status}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-muted-foreground text-xs max-w-xs truncate" title={s.error}>
                              {s.error || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Click &quot;Test all sources&quot; above to validate each feed.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
