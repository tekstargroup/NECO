"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth, useOrganization } from "@clerk/nextjs"

import { useApiClient, formatApiError } from "@/lib/api-client-client"
import { useDevAuthContext } from "@/contexts/dev-auth-context"
import { ShipmentDetailShell } from "@/components/shipment-detail-shell"

interface ShipmentDetailPageProps {
  params: {
    shipmentId: string
  }
}

export default function ShipmentDetailPage({ params }: ShipmentDetailPageProps) {
  const { shipmentId } = params
  const router = useRouter()
  const { apiGet } = useApiClient()
  const { isDevAuth: serverDevAuth } = useDevAuthContext()
  const { isLoaded: authLoaded } = useAuth()
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const [shipment, setShipment] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const canLoad = serverDevAuth || (authLoaded && orgLoaded && organization?.id)

  useEffect(() => {
    if (!canLoad) return
    if (!serverDevAuth && !organization?.id) {
      router.replace("/app/organizations/select")
      return
    }

    let cancelled = false

    const loadShipment = async () => {
      try {
        const data = await apiGet(`/api/v1/shipments/${shipmentId}`)
        if (!cancelled) {
          setShipment(data)
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(formatApiError(e as import("@/lib/api-client-client").ApiClientError))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadShipment()
    return () => {
      cancelled = true
    }
  }, [apiGet, shipmentId, canLoad, serverDevAuth, organization?.id, router])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Loading shipment...</p>
        </div>
      </div>
    )
  }

  if (error || !shipment) {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error || "Shipment not found"}</p>
        </div>
      </div>
    )
  }

  return <ShipmentDetailShell shipment={shipment} shipmentId={shipmentId} />
}
