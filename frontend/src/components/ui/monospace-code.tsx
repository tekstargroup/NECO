/**
 * MonospaceCode - Sprint 12
 * 
 * Displays HTS codes and other monospace values.
 */

import { cn } from "@/lib/utils"

interface MonospaceCodeProps {
  children: React.ReactNode
  className?: string
}

export function MonospaceCode({ children, className }: MonospaceCodeProps) {
  return (
    <code className={cn("font-mono text-sm bg-muted px-1.5 py-0.5 rounded", className)}>
      {children}
    </code>
  )
}
