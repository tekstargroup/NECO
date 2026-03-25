"use client"

import { useState, useEffect, useRef } from "react"
import { FileText, ClipboardList, Hash, CheckCircle } from "lucide-react"

const STEP_COUNT = 4
const STEP_PCT = 100 / STEP_COUNT
const TRUST_MICRO_COPY = [
  "Reading uploaded documents and extracted fields",
  "Comparing product data with tariff and regulatory references",
  "Building likely HS code suggestions with supporting evidence",
]

/**
 * Step config: label for the segment, statusMessage shown below the bar.
 */
const STEPS = [
  {
    id: "documents",
    number: 1,
    label: "Analyzing Documents",
    statusMessage: "Analyzing documents provided.",
  },
  {
    id: "compare",
    number: 2,
    label: "Comparing Data",
    statusMessage: "Comparing extracted product data against tariff and regulatory references.",
  },
  {
    id: "suggestions",
    number: 3,
    label: "Forming Suggestions",
    statusMessage: "Forming likely HS code suggestions with evidence support.",
  },
  {
    id: "completed",
    number: 4,
    label: "Completed",
    statusMessage: "Analysis complete. View your results below.",
  },
] as const

function formatRemainingMinutes(seconds: number, currentStepIndex: number): string {
  if (currentStepIndex === STEPS.length - 1) return "Results will appear when ready."
  if (currentStepIndex === STEPS.length - 2) return "Almost done…"
  if (seconds <= 0) return "Completing final checks…"
  const m = Math.ceil(seconds / 60)
  if (m <= 1) return "Less than a minute remaining"
  return `About ${m} minutes remaining`
}

interface AnalysisProgressTrackerProps {
  /** Estimated total duration in seconds. Typical run: 1–3 min; default 180 (3 min). */
  estimatedTotalSeconds?: number
  /** When RUNNING/QUEUED we never show "Completed" (step 6) until server is COMPLETE. */
  serverStatus?: string
  /** Called when user clicks the Completed step (e.g. scroll to results or go to Reviews) */
  onCompletedStepClick?: () => void
}

export function AnalysisProgressTracker({
  estimatedTotalSeconds = 180,
  serverStatus,
  onCompletedStepClick,
}: AnalysisProgressTrackerProps) {
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef<number>(Date.now())

  useEffect(() => {
    startRef.current = Date.now()
    setElapsed(0)
  }, [])

  useEffect(() => {
    const tick = () => {
      const now = Date.now()
      const sec = Math.floor((now - startRef.current) / 1000)
      setElapsed(sec)
    }
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [])

  const progress = Math.min(100, (elapsed / estimatedTotalSeconds) * 100)
  const remaining = Math.max(0, estimatedTotalSeconds - elapsed)
  const timeBasedStep = Math.min(STEPS.length - 1, Math.floor(progress / STEP_PCT))
  // Never show "Completed" until server actually says COMPLETE
  const isStillWaiting = serverStatus === "RUNNING" || serverStatus === "QUEUED"
  const currentStepIndex = isStillWaiting ? Math.min(timeBasedStep, STEPS.length - 2) : timeBasedStep
  const currentStep = STEPS[currentStepIndex]
  const rotatingMessage = TRUST_MICRO_COPY[Math.floor(elapsed / 3) % TRUST_MICRO_COPY.length]

  const statusIcons = [
    <FileText key="doc" className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />,
    <ClipboardList key="duty" className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />,
    <Hash key="codes" className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />,
    <CheckCircle key="done" className="h-5 w-5 shrink-0 text-green-600" aria-hidden />,
  ]

  return (
    <div className="w-full space-y-6">
      <div className="space-y-5">
        <div
          className="flex w-full overflow-hidden rounded-xl border border-border bg-muted/50 shadow-sm"
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Analysis in progress: ${currentStep.label}`}
        >
          {STEPS.map((step, i) => {
            const isComplete = i < currentStepIndex
            const isCurrent = i === currentStepIndex
            const segmentProgress =
              isComplete
                ? 100
                : isCurrent
                ? ((progress - i * STEP_PCT) / STEP_PCT) * 100
                : 0

            const isCompletedStep = step.id === "completed"
            const isClickable = isCompletedStep && (isComplete || isCurrent) && onCompletedStepClick
            const showFill = isCurrent && !isCompletedStep && segmentProgress > 0

            return (
              <div
                key={step.id}
                className={`relative flex flex-1 flex-col items-center justify-center overflow-hidden py-4 transition-all duration-500 ease-out ${
                  isCurrent
                    ? "z-10 scale-[1.02] rounded-lg border-2 border-primary bg-primary text-primary-foreground shadow-lg"
                    : isComplete
                    ? "rounded-none bg-primary/80 text-primary-foreground"
                    : "rounded-none bg-muted/80 text-muted-foreground"
                } ${isClickable ? "cursor-pointer hover:opacity-95" : ""}`}
                style={{
                  marginLeft: isCurrent ? 2 : 0,
                  marginRight: isCurrent ? 2 : 0,
                }}
                role={isClickable ? "button" : undefined}
                tabIndex={isClickable ? 0 : undefined}
                onClick={isClickable ? onCompletedStepClick : undefined}
                onKeyDown={
                  isClickable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          onCompletedStepClick()
                        }
                      }
                    : undefined
                }
                aria-label={isClickable ? "Go to results" : undefined}
              >
                {/* Segment fill: left-to-right fill for current step (not Completed) */}
                {showFill && (
                  <div
                    className="absolute inset-0 bg-primary-foreground/20 transition-[width] duration-700 ease-out"
                    style={{ width: `${segmentProgress}%`, left: 0 }}
                  />
                )}
                <span className="relative z-10 text-lg font-bold tabular-nums">
                  {step.number}
                </span>
                <span className="relative z-10 mt-0.5 text-center text-xs font-medium leading-tight">
                  {step.label}
                </span>
                {isComplete && (
                  <span className="relative z-10 mt-1 text-xs font-bold text-primary-foreground" aria-hidden>
                    ✓
                  </span>
                )}
              </div>
            )
          })}
        </div>

        <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/20 px-4 py-3 shadow-sm transition-colors duration-300">
          {statusIcons[currentStepIndex]}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground">
              {currentStep.statusMessage}
            </p>
            {currentStepIndex < STEPS.length - 1 && (
              <p className="mt-0.5 text-xs text-muted-foreground/90">{rotatingMessage}</p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              {formatRemainingMinutes(remaining, currentStepIndex)}
            </p>
            {currentStepIndex === STEPS.length - 1 && remaining <= 0 && (
              <p className="mt-0.5 text-xs text-muted-foreground/90">
                You can also click <strong>Check for results</strong> below—it does not restart analysis.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
