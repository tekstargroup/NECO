/**
 * EligibilityBadge - Sprint 12
 * 
 * Shows shipment eligibility status.
 * Conservative: readiness wording (not "eligible" as a legal guarantee).
 */

import { cn } from "@/lib/utils"

interface EligibilityBadgeProps {
  eligible: boolean
  missingRequirements?: string[]
  className?: string
}

export function EligibilityBadge({ eligible, missingRequirements = [], className }: EligibilityBadgeProps) {
  if (eligible) {
    return (
      <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 border border-blue-300", className)}>
        Ready to run analysis
      </span>
    )
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 border border-orange-300 w-fit">
        Not ready — requirements missing
      </span>
      {missingRequirements.length > 0 && (
        <span className="text-xs text-muted-foreground">
          Missing: {missingRequirements.join(", ")}
        </span>
      )}
    </div>
  )
}
