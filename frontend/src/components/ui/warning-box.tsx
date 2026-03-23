/**
 * WarningBox - Sprint 12
 * 
 * Displays warnings (e.g., document processing errors).
 * Clear, not alarming, but visible.
 */

import { Card, CardContent, CardHeader, CardTitle } from "./card"
import { AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

interface WarningBoxProps {
  title?: string
  warnings: Array<{ type?: string; message: string; document_id?: string }>
  className?: string
}

export function WarningBox({ title = "Warnings", warnings, className }: WarningBoxProps) {
  if (!warnings || warnings.length === 0) {
    return null
  }

  return (
    <Card className={cn("border-yellow-300 bg-yellow-50", className)}>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {warnings.map((warning, index) => (
            <li key={index} className="text-muted-foreground">
              {warning.message}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
