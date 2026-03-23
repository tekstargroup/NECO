/**
 * BlockerBox - Sprint 12
 * 
 * Displays blockers with title and bullet reasons.
 * Conservative, clear, no decorative styling.
 */

import { Card, CardContent, CardHeader, CardTitle } from "./card"

interface BlockerBoxProps {
  title: string
  blockers: string[]
  className?: string
}

export function BlockerBox({ title, blockers, className }: BlockerBoxProps) {
  if (!blockers || blockers.length === 0) {
    return null
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
          {blockers.map((blocker, index) => (
            <li key={index}>{blocker}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
