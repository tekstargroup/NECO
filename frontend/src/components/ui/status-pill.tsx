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
  COMPLETE: "bg-slate-100 text-slate-700 border-slate-300", // Neutral, not green
  REFUSED: "bg-orange-100 text-orange-700 border-orange-300",
  FAILED: "bg-red-100 text-red-700 border-red-300",
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
      {status}
    </span>
  )
}
