/**
 * Overview Tab - Sprint 12
 * 
 * Shows shipment summary, eligibility, entitlement usage, latest analysis status.
 */

"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { KeyValueRow } from "@/components/ui/key-value-row"
import { StatusPill } from "@/components/ui/status-pill"
import { EligibilityBadge } from "@/components/ui/eligibility-badge"
import { useApiClient } from "@/lib/api-client-client"

interface OverviewTabProps {
  shipment: any
  shipmentId: string
}

export function OverviewTab({ shipment, shipmentId }: OverviewTabProps) {
  const [entitlement, setEntitlement] = useState<{ shipments_used: number; limit: number } | null>(null)
  const eligibility = shipment.eligibility || { eligible: false, missing_requirements: [], satisfied_path: null }

  useEffect(() => {
    // TODO: Fetch entitlement if endpoint exists
    // For now, derive from shipments
    setEntitlement({ shipments_used: 0, limit: 15 })
  }, [])

  return (
    <div className="space-y-6">
      {shipment.status === "FAILED" && eligibility.eligible && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="pt-6">
            <p className="text-sm text-amber-800">
              Analysis failed on a previous run. Use <strong>Re-run</strong> in the header above to try again with the same documents (no need to re-upload).
            </p>
          </CardContent>
        </Card>
      )}

      {/* Shipment Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Shipment Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <KeyValueRow label="Name" value={shipment.name} />
          <KeyValueRow label="Status" value={<StatusPill status={shipment.status} />} />
          <KeyValueRow
            label="Eligibility"
            value={
              <EligibilityBadge
                eligible={eligibility.eligible}
                missingRequirements={eligibility.missing_requirements}
              />
            }
          />
          {eligibility.satisfied_path && (
            <KeyValueRow
              label="Eligibility Path"
              value={eligibility.satisfied_path.replace(/_/g, " ")}
            />
          )}
          <KeyValueRow
            label="Date added"
            value={new Date(shipment.created_at).toLocaleString()}
          />
          <KeyValueRow
            label="Entry Date"
            value={
              shipment.references?.find((r: any) => r.key === "ENTRY_DATE")?.value ||
              shipment.references?.find((r: any) => r.key === "ENTRY")?.value ||
              "—"
            }
          />
        </CardContent>
      </Card>

      {/* Entitlement Usage */}
      {entitlement && (
        <Card>
          <CardHeader>
            <CardTitle>Entitlement Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              This month: {entitlement.shipments_used} of {entitlement.limit} shipments used
            </p>
          </CardContent>
        </Card>
      )}

      {/* Latest Analysis */}
      {shipment.latest_analysis_status && (
        <Card>
          <CardHeader>
            <CardTitle>Latest Analysis</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <KeyValueRow
              label="Status"
              value={<StatusPill status={shipment.latest_analysis_status} />}
            />
            {shipment.latest_analysis_id && (
              <KeyValueRow
                label="Analysis ID"
                value={<code className="text-xs">{shipment.latest_analysis_id}</code>}
              />
            )}
            {shipment.latest_review_id && (
              <KeyValueRow
                label="Review ID"
                value={<code className="text-xs">{shipment.latest_review_id}</code>}
              />
            )}
          </CardContent>
        </Card>
      )}

      {/* References */}
      {shipment.references && shipment.references.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>References</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {shipment.references.map((ref: any, index: number) => (
              <KeyValueRow
                key={index}
                label={ref.key}
                value={ref.value}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Items */}
      {shipment.items && shipment.items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {shipment.items.map((item: any, index: number) => (
                <div key={item.id || index} className="border rounded-lg p-4 space-y-2">
                  <KeyValueRow label="Label" value={item.label} />
                  {item.declared_hts_code && (
                    <KeyValueRow
                      label="Declared HTS"
                      value={<code className="text-xs">{item.declared_hts_code}</code>}
                    />
                  )}
                  {item.value && (
                    <KeyValueRow
                      label="Value"
                      value={`${item.currency || "USD"} ${item.value}`}
                    />
                  )}
                  {item.quantity && (
                    <KeyValueRow
                      label="Quantity"
                      value={`${item.quantity} ${item.uom || ""}`}
                    />
                  )}
                  {item.country_of_origin && (
                    <KeyValueRow label="Country of Origin" value={item.country_of_origin} />
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
