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
import { ErrorBoundary } from "@/components/ui/error-boundary"

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
  const shipmentTypeRef = (shipment?.references || []).find((r: any) => String(r?.key || "").toUpperCase() === "SHIPMENT_TYPE")
  const shipmentType = String(shipmentTypeRef?.value || "PRE_COMPLIANCE").toUpperCase()
  const isPreCompliance = shipmentType !== "ENTRY_COMPLIANCE"
  const shipmentTypeLabel = isPreCompliance ? "Pre-Compliance" : "Entry Compliance"

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
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${isPreCompliance ? "bg-blue-100 text-blue-800" : "bg-emerald-100 text-emerald-800"}`}>
              {shipmentTypeLabel}
            </span>
            {activeTab === "documents" && !eligibility.eligible ? (
              <span className="text-sm text-muted-foreground">
                {isPreCompliance
                  ? "Upload documents to estimate likely HS code and risks before filing."
                  : "Upload entry documents to run filing-oriented compliance review."}
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
          <div className="ml-auto flex items-center gap-2">
            {isPreCompliance && (
              <Button
                type="button"
                variant="outline"
                title="Promotion workflow lands in Sprint 14.5"
                onClick={() => setActiveTab("documents")}
              >
                Promote to Entry Compliance
              </Button>
            )}
            <Button
              onClick={handleAnalyzeClick}
            >
              {shipment.status === "FAILED" ? "Re-run" : "Analyze Shipment"}
            </Button>
          </div>
        )}
      </div>

      {isPreCompliance && (
        <div className="rounded-lg border border-blue-200 bg-blue-50/70 px-4 py-3">
          <p className="text-sm font-medium text-blue-900">Pre-Compliance mode</p>
          <p className="text-sm text-blue-800 mt-1">
            This mode is advisory. Use it to estimate likely HS code, evidence strength, and review needs before shipment is filed.
          </p>
          <ul className="mt-2 text-xs text-blue-800 list-disc list-inside">
            <li>When final entry docs are available, promote this shipment to Entry Compliance.</li>
            <li>Entry Compliance adds stricter filing-oriented checks and readiness gating.</li>
          </ul>
        </div>
      )}

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
          <ErrorBoundary tabName="Overview">
            <OverviewTab shipment={shipment} shipmentId={shipmentId} />
          </ErrorBoundary>
        </div>
        <div className={activeTab === "documents" ? "" : "hidden"}>
          <ErrorBoundary tabName="Documents">
            <DocumentsTab
              shipment={shipment}
              shipmentId={shipmentId}
              onRunPreComplianceAnalysis={handleAnalyzeClick}
            />
          </ErrorBoundary>
        </div>
        <div className={activeTab === "analysis" ? "" : "hidden"}>
          <ErrorBoundary tabName="Analysis">
            <AnalysisTab
              shipment={shipment}
              shipmentId={shipmentId}
              autoStartAnalysis={autoStartAnalysis}
              onAutoStartComplete={() => setAutoStartAnalysis(false)}
              onSwitchToReviews={() => setActiveTab("reviews")}
              onSwitchToDocuments={() => setActiveTab("documents")}
              onSwitchToExports={() => setActiveTab("exports")}
            />
          </ErrorBoundary>
        </div>
        <div className={activeTab === "reviews" ? "" : "hidden"}>
          <ErrorBoundary tabName="Reviews">
            <ReviewsTab shipment={shipment} shipmentId={shipmentId} />
          </ErrorBoundary>
        </div>
        <div className={activeTab === "exports" ? "" : "hidden"}>
          <ErrorBoundary tabName="Exports">
            <ExportsTab
              shipment={shipment}
              shipmentId={shipmentId}
              onSwitchToReviews={() => setActiveTab("reviews")}
            />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
