/**
 * Shipment Detail Shell - Sprint 12
 * 
 * Tabbed interface for shipment details.
 */

"use client"

import { useState } from "react"
import { StatusPill } from "@/components/ui/status-pill"
import { EligibilityBadge } from "@/components/ui/eligibility-badge"
import { Button } from "@/components/ui/button"
import { OverviewTab } from "./shipment-tabs/overview-tab"
import { DocumentsTab } from "./shipment-tabs/documents-tab"
import { AnalysisTab } from "./shipment-tabs/analysis-tab"
import { ReviewsTab } from "./shipment-tabs/reviews-tab"
import { ExportsTab } from "./shipment-tabs/exports-tab"

interface ShipmentDetailShellProps {
  shipment: any
  shipmentId: string
}

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "documents", label: "Documents" },
  { id: "analysis", label: "Analysis" },
  { id: "reviews", label: "Reviews" },
  { id: "exports", label: "Exports" },
] as const

export function ShipmentDetailShell({ shipment, shipmentId }: ShipmentDetailShellProps) {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]["id"]>("documents")
  const [autoStartAnalysis, setAutoStartAnalysis] = useState(false)
  const eligibility = shipment.eligibility || { eligible: false, missing_requirements: [], satisfied_path: null }

  const handleAnalyzeClick = () => {
    setAutoStartAnalysis(true)
    setActiveTab("analysis")
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{shipment.name}</h1>
          <div className="flex gap-4 mt-2">
            <StatusPill status={shipment.status} />
            {activeTab === "documents" && !eligibility.eligible ? (
              <span className="text-sm text-muted-foreground">
                Upload documents to get started.
              </span>
            ) : (
              <EligibilityBadge
                eligible={eligibility.eligible}
                missingRequirements={eligibility.missing_requirements}
              />
            )}
          </div>
        </div>
        {eligibility.eligible && (shipment.status === "READY" || shipment.status === "FAILED") && (
          <Button
            onClick={handleAnalyzeClick}
            className="ml-auto"
          >
            {shipment.status === "FAILED" ? "Re-run" : "Analyze Shipment"}
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b">
        <nav className="flex gap-4">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id)
                if (tab.id !== "analysis") setAutoStartAnalysis(false)
              }}
              className={`px-4 py-2 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-primary font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content — keep Analysis mounted when hidden so state (result_json) persists when switching Review → Analysis */}
      <div>
        <div className={activeTab === "overview" ? "" : "hidden"}>
          <OverviewTab shipment={shipment} shipmentId={shipmentId} />
        </div>
        <div className={activeTab === "documents" ? "" : "hidden"}>
          <DocumentsTab shipment={shipment} shipmentId={shipmentId} />
        </div>
        <div className={activeTab === "analysis" ? "" : "hidden"}>
          <AnalysisTab
            shipment={shipment}
            shipmentId={shipmentId}
            autoStartAnalysis={autoStartAnalysis}
            onAutoStartComplete={() => setAutoStartAnalysis(false)}
            onSwitchToReviews={() => setActiveTab("reviews")}
            onSwitchToDocuments={() => setActiveTab("documents")}
            onSwitchToExports={() => setActiveTab("exports")}
          />
        </div>
        <div className={activeTab === "reviews" ? "" : "hidden"}>
          <ReviewsTab shipment={shipment} shipmentId={shipmentId} />
        </div>
        <div className={activeTab === "exports" ? "" : "hidden"}>
          <ExportsTab
            shipment={shipment}
            shipmentId={shipmentId}
            onSwitchToReviews={() => setActiveTab("reviews")}
          />
        </div>
      </div>
    </div>
  )
}
