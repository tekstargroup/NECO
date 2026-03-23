"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Plus, Trash2 } from "lucide-react"
import { useAuth, useOrganization } from "@clerk/nextjs"

import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { StatusPill } from "@/components/ui/status-pill"
import { EligibilityBadge } from "@/components/ui/eligibility-badge"
import { Button } from "@/components/ui/button"

interface ShipmentListItem {
  shipment_id: string
  name: string
  status: string
  created_at: string
  updated_at: string
  eligibility: {
    eligible: boolean
    missing_requirements?: string[]
    eligibility_path?: string
  }
}

export default function ShipmentsPage() {
  const router = useRouter()
  const { apiGet, apiDelete, effectiveOrgId, useDevAuth } = useApiClient()
  const { isLoaded: authLoaded } = useAuth()
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const resolvedOrgId =
    effectiveOrgId ||
    organization?.id ||
    process.env.NEXT_PUBLIC_TEST_ORG_ID ||
    null
  const [shipments, setShipments] = useState<ShipmentListItem[]>([])
  const [entitlement, setEntitlement] = useState<{ shipments_used: number; shipments_limit: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!useDevAuth && (!authLoaded || !orgLoaded)) {
      return
    }
    if (!resolvedOrgId) {
      if (!useDevAuth) router.replace("/app/organizations/select")
      return
    }

    let cancelled = false

    const loadShipments = async () => {
      try {
        const [shipsData, entData] = await Promise.all([
          apiGet<ShipmentListItem[]>("/api/v1/shipments"),
          apiGet<{ shipments_used: number; shipments_limit: number }>("/api/v1/shipments/entitlement"),
        ])
        if (!cancelled) {
          setShipments(shipsData)
          setEntitlement(entData)
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

    loadShipments()
    return () => {
      cancelled = true
    }
  }, [apiGet, authLoaded, orgLoaded, resolvedOrgId, useDevAuth, router])

  const handleDelete = async (e: React.MouseEvent, shipmentId: string, name: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
    setDeletingId(shipmentId)
    setError(null)
    try {
      await apiDelete(`/api/v1/shipments/${shipmentId}`)
      setShipments((prev) => prev.filter((s) => s.shipment_id !== shipmentId))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(shipmentId)
        return next
      })
    } catch (err: unknown) {
      setError(formatApiError(err as ApiClientError))
    } finally {
      setDeletingId(null)
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === shipments.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(shipments.map((s) => s.shipment_id)))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Delete ${selectedIds.size} selected shipment(s)? This cannot be undone.`)) return
    setError(null)
    const ids = Array.from(selectedIds)
    let successCount = 0
    for (const id of ids) {
      try {
        await apiDelete(`/api/v1/shipments/${id}`)
        setShipments((prev) => prev.filter((s) => s.shipment_id !== id))
        successCount++
      } catch {
        // Individual failure - keep going
      }
    }
    setSelectedIds(new Set())
    if (successCount < ids.length) {
      setError(`Deleted ${successCount} of ${ids.length}. Some could not be deleted (have documents or analyses).`)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Shipments</h1>
        <Link href="/app/shipments/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Shipment
          </Button>
        </Link>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-700">
          This month: {entitlement ? `${entitlement.shipments_used} of ${entitlement.shipments_limit}` : "—"} analyses used
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <Button variant="destructive" size="sm" onClick={handleBulkDelete} disabled={!!deletingId}>
            Delete selected
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>
            Clear selection
          </Button>
        </div>
      )}

      <div className="border rounded-lg">
        <table className="w-full">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 w-10">
                <input
                  type="checkbox"
                  checked={shipments.length > 0 && selectedIds.size === shipments.length}
                  onChange={toggleSelectAll}
                  className="rounded"
                />
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium">Name</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Eligibility</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Created</th>
              <th className="px-4 py-3 text-right text-sm font-medium w-12">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                  Loading shipments...
                </td>
              </tr>
            ) : shipments.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No shipments yet. Create your first shipment to get started.
                </td>
              </tr>
            ) : (
              shipments.map((shipment) => (
                <tr
                  key={shipment.shipment_id}
                  className="border-t hover:bg-muted/50 cursor-pointer"
                  onClick={() => router.push(`/app/shipments/${shipment.shipment_id}`)}
                >
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(shipment.shipment_id)}
                      onChange={() => toggleSelect(shipment.shipment_id)}
                      onClick={(e) => e.stopPropagation()}
                      className="rounded"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/app/shipments/${shipment.shipment_id}`}
                      className="font-medium hover:underline"
                    >
                      {shipment.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={shipment.status} />
                  </td>
                  <td className="px-4 py-3">
                    <EligibilityBadge
                      eligible={shipment.eligibility.eligible}
                      missingRequirements={shipment.eligibility.missing_requirements}
                    />
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {new Date(shipment.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={(e) => handleDelete(e, shipment.shipment_id, shipment.name)}
                      disabled={deletingId === shipment.shipment_id}
                      title="Delete shipment"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
