/**
 * KeyValueRow - Sprint 12
 * 
 * Simple key-value display component.
 */

interface KeyValueRowProps {
  label: string
  value: React.ReactNode
  className?: string
}

export function KeyValueRow({ label, value, className }: KeyValueRowProps) {
  return (
    <div className={`flex justify-between py-2 border-b ${className}`}>
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  )
}
