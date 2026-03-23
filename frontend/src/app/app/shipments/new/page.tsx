/**
 * Create Shipment Page - Sprint 12
 */

"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth, useOrganization } from "@clerk/nextjs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useApiClient, ApiClientError, formatApiError } from "@/lib/api-client-client"
import { useDevAuthContext } from "@/contexts/dev-auth-context"

export default function NewShipmentPage() {
  const router = useRouter()
  const { apiPost, effectiveOrgId, useDevAuth } = useApiClient()
  const { isDevAuth: serverDevAuth, orgId: serverOrgId } = useDevAuthContext()
  const { isLoaded: authLoaded } = useAuth()
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const resolvedOrgId =
    (serverDevAuth ? serverOrgId : null) ??
    effectiveOrgId ??
    organization?.id ??
    process.env.NEXT_PUBLIC_TEST_ORG_ID ??
    null
  const canSubmit =
    serverDevAuth ||
    useDevAuth ||
    (authLoaded && orgLoaded && (organization?.id || effectiveOrgId))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    name: "",
    references: [] as Array<{ key: string; value: string }>,
    items: [] as Array<{
      label: string
      declared_hts_code?: string
      value?: string
      currency?: string
      quantity?: string
      uom?: string
      country_of_origin?: string
    }>,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!serverDevAuth && !useDevAuth && (!authLoaded || !orgLoaded)) {
      setError("Authentication context still loading. Please try again.")
      return
    }
    if (!resolvedOrgId) {
      if (!serverDevAuth && !useDevAuth) router.replace("/app/organizations/select")
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await apiPost<{ shipment_id: string }>("/api/v1/shipments", {
        name: formData.name,
        references: formData.references.map((r) => ({
          key: r.key,
          value: r.value,
        })),
        items: formData.items.map((item) => ({
          label: item.label,
          declared_hts_code: item.declared_hts_code || null,
          value: item.value ? parseFloat(item.value) : null,
          currency: item.currency || null,
          quantity: item.quantity ? parseFloat(item.quantity) : null,
          uom: item.uom || null,
          country_of_origin: item.country_of_origin || null,
        })),
      })

      router.push(`/app/shipments/${response.shipment_id}`)
    } catch (e: unknown) {
      setError(formatApiError(e as ApiClientError) || "Failed to create shipment")
    } finally {
      setLoading(false)
    }
  }

  const addReference = () => {
    setFormData({
      ...formData,
      references: [...formData.references, { key: "", value: "" }],
    })
  }

  const removeReference = (index: number) => {
    setFormData({
      ...formData,
      references: formData.references.filter((_, i) => i !== index),
    })
  }

  const updateReference = (index: number, field: "key" | "value", value: string) => {
    const updated = [...formData.references]
    updated[index] = { ...updated[index], [field]: value }
    setFormData({ ...formData, references: updated })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">New Shipment</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Shipment Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Shipment Name *
              </label>
              <input
                id="name"
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                maxLength={255}
              />
            </div>

            {/* References */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium">References (Optional)</label>
                <Button type="button" variant="outline" size="sm" onClick={addReference}>
                  Add Reference
                </Button>
              </div>
              {formData.references.map((ref, index) => (
                <div key={index} className="flex gap-2 mb-2">
                  <input
                    type="text"
                    placeholder="Type (PO, Entry, etc.)"
                    value={ref.key}
                    onChange={(e) => updateReference(index, "key", e.target.value)}
                    className="flex-1 px-3 py-2 border rounded-md text-sm"
                  />
                  <input
                    type="text"
                    placeholder="Value"
                    value={ref.value}
                    onChange={(e) => updateReference(index, "value", e.target.value)}
                    className="flex-1 px-3 py-2 border rounded-md text-sm"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeReference(index)}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="flex gap-4">
          <Button
            type="submit"
            disabled={loading || !canSubmit || !resolvedOrgId}
          >
            {loading ? "Creating..." : "Create Shipment"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
