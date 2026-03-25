/**
 * StatusPill - Sprint 12
 * 
 * Displays shipment/analysis status with appropriate styling.
 * Non-negotiable: no green checkmarks as "safe".
 */

import { cn } from "@/lib/utils"

export type ShipmentStatus = "DRAFT" | "READY" | "ANALYZING" | "COMPLETE" | "REFUSED" | "FAILED"
export type AnalysisStatus = "QUEUED" | "RUNNING" | "COMPLETE" | "FAILED" | "REFUSED"

interface StatusPillProps {
  status: ShipmentStatus | AnalysisStatus | string
  className?: string
}

const statusColors: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700 border-gray-300",
  READY: "bg-blue-100 text-blue-700 border-blue-300",
  ANALYZING: "bg-yellow-100 text-yellow-700 border-yellow-300",
  QUEUED: "bg-yellow-100 text-yellow-700 border-yellow-300",
  RUNNING: "bg-yellow-100 text-yellow-700 border-yellow-300",
  PROCESSING: "bg-blue-100 text-blue-700 border-blue-300",
  COMPLETE: "bg-slate-100 text-slate-700 border-slate-300",
  COMPLETED: "bg-green-100 text-green-700 border-green-300",
  REFUSED: "bg-orange-100 text-orange-700 border-orange-300",
  FAILED: "bg-red-100 text-red-700 border-red-300",
  REVIEW_REQUIRED: "bg-red-100 text-red-700 border-red-300",
  PARTIALLY_REVIEWED: "bg-amber-100 text-amber-700 border-amber-300",
  REVIEWED_ACCEPTED: "bg-green-100 text-green-700 border-green-300",
  REVIEWED_REJECTED: "bg-red-100 text-red-700 border-red-300",
  BLOCKED: "bg-red-100 text-red-700 border-red-300",
  EXPORTED: "bg-green-100 text-green-700 border-green-300",
  EXPORT_PENDING: "bg-amber-100 text-amber-700 border-amber-300",
}

const displayLabels: Record<string, string> = {
  COMPLETE: "ANALYSIS GENERATED",
  READY: "READY FOR CLASSIFICATION",
  REVIEW_REQUIRED: "REVIEW REQUIRED",
  PARTIALLY_REVIEWED: "PARTIALLY REVIEWED",
  REVIEWED_ACCEPTED: "ACCEPTED",
  REVIEWED_REJECTED: "REJECTED",
  BLOCKED: "BLOCKED",
  PROCESSING: "PROCESSING",
  COMPLETED: "COMPLETED",
  EXPORTED: "EXPORTED",
  EXPORT_PENDING: "EXPORT PENDING",
}

export function StatusPill({ status, className }: StatusPillProps) {
  const colors = statusColors[status] || "bg-gray-100 text-gray-700 border-gray-300"
  
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        colors,
        className
      )}
    >
      {displayLabels[status] || status}
    </span>
  )
}
