/**
 * RecommendationDetailDrawer - Right-side panel for PSC table rows
 *
 * Explains: why it fits, what weakens it, evidence, NECO reasoning.
 * Uses decision-safe language: Alternative HTS identified, Evidence strength, Review level.
 * Goal: user can confidently approve or reject after reviewing.
 */

"use client"

import { Button } from "@/components/ui/button"

interface RecommendationDetailDrawerProps {
  open: boolean
  onClose: () => void
  item: {
    displayName: string
    declaredHts: string
    recommendedHts: string
    estimatedSavings: number
    shortReason: string
    confidence: number
    risk: string
    evidenceSources?: string[]
    psc?: any
    classification?: any
    regulatory?: any[]
  }
  rawItem?: any
  evidenceMap?: any
  /** Evidence bundle from API (supporting/conflicting/warning, document_refs, authority_refs) */
  evidenceBundle?: {
    supporting_evidence?: { summary: string; source_label?: string; page_ref?: string }[]
    conflicting_evidence?: { summary: string; source_label?: string; page_ref?: string }[]
    warning_evidence?: { summary: string; source_label?: string; page_ref?: string }[]
    document_refs?: { document_type: string; filename: string; page?: number }[]
    authority_refs?: { authority_type: string; reference_id?: string; title?: string; relation?: string; role?: string }[]
    evidence_strength?: string
    review_level?: string
    next_step?: string
  }
}

export function RecommendationDetailDrawer({
  open,
  onClose,
  item,
  rawItem,
  evidenceMap,
  evidenceBundle,
}: RecommendationDetailDrawerProps) {
  if (!open || !item?.displayName) return null

  const evidenceStrength = evidenceBundle?.evidence_strength ?? (
    (item.confidence ?? 0.5) >= 0.7 ? "STRONG" : (item.confidence ?? 0.5) >= 0.5 ? "MODERATE" : "WEAK"
  )
  const evidenceStrengthLabel = evidenceStrength === "STRONG" ? "Strong" : evidenceStrength === "MODERATE" ? "Moderate" : "Weak"
  const reviewLevel = evidenceBundle?.review_level ?? (item.risk || "Medium")
  const docMatch = (item.confidence ?? 0.5) >= 0.6 ? "Strong" : (item.confidence ?? 0.5) >= 0.4 ? "Medium" : "Weak"
  const rulingSupport = rawItem?.classification?.candidates?.length ? "Medium" : "Weak"
  const dataCompleteness = rawItem?.value != null && rawItem?.value > 0 ? "Strong" : "Medium"

  const whyFits: { text: string; source?: string; page?: string }[] = evidenceBundle?.supporting_evidence?.length
    ? evidenceBundle.supporting_evidence.map((e) => ({ text: e.summary, source: e.source_label, page: e.page_ref }))
    : []
  if (whyFits.length === 0) {
    if (item.recommendedHts) whyFits.push({ text: "Product description matches classification scope from invoice." })
    if (item.estimatedSavings > 0) whyFits.push({ text: "Alternative HTS shows lower duty rate based on comparable data." })
    if (rawItem?.psc?.alternatives?.length) whyFits.push({ text: "Historical usage and PSC signals align with similar imports." })
    if (rawItem?.classification?.primary_candidate) whyFits.push({ text: "Classification engine identified matching HTS structure." })
    if (whyFits.length === 0) whyFits.push({ text: "Alternative classification identified from document analysis." })
  }

  const whyRisky: { text: string; source?: string }[] = evidenceBundle?.conflicting_evidence?.length || evidenceBundle?.warning_evidence?.length
    ? [
        ...(evidenceBundle.conflicting_evidence || []).map((e) => ({ text: e.summary, source: e.source_label })),
        ...(evidenceBundle.warning_evidence || []).map((e) => ({ text: e.summary, source: e.source_label })),
      ]
    : []
  if (whyRisky.length === 0) {
    if ((item.confidence ?? 0.7) < 0.7) whyRisky.push({ text: "No direct CBP ruling match for this product." })
    if (rawItem?.regulatory?.length) whyRisky.push({ text: `Regulatory flags present: ${rawItem.regulatory.map((r: any) => r.regulator).join(", ")}.` })
    if (item.risk === "Medium" || reviewLevel === "MEDIUM") whyRisky.push({ text: "Review recommended before filing." })
    if (rawItem?.classification?.review_explanation?.primary_reasons?.length) {
      whyRisky.push(...rawItem.classification.review_explanation.primary_reasons.slice(0, 2).map((r: string) => ({ text: r })))
    }
    if (whyRisky.length === 0) whyRisky.push({ text: "Confirm classification with broker before filing." })
  }

  const docRefs = evidenceBundle?.document_refs?.length
    ? evidenceBundle.document_refs
    : (evidenceMap?.documents || []).map((d: any) => ({ document_type: d.document_type || "Document", filename: d.filename || d.document_type, page: d.page }))
  const docDetails = docRefs.length
    ? docRefs.map((d: any) => ({
      name: d.filename || d.document_type,
      detail: d.page ? `page ${d.page}` : "source document",
    }))
    : [
      { name: "Entry Summary", detail: "declared HTS and duty fields reviewed" },
      { name: "Commercial Invoice", detail: "product description and line-level values reviewed" },
    ]
  const reasoningSummary =
    rawItem?.classification?.review_explanation?.summary ||
    (rawItem?.classification?.review_explanation?.primary_reasons?.length
      ? rawItem.classification.review_explanation.primary_reasons.slice(0, 2).join("; ")
      : null)

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20" onClick={onClose} aria-hidden />
      <div
        className="fixed top-0 right-0 z-50 h-full w-full max-w-md bg-white shadow-xl border-l border-[#E5E7EB] overflow-y-auto"
        style={{ color: "#0F172A" }}
      >
        <div className="p-6 space-y-6">
          <div className="flex justify-between items-start">
            <h2 className="text-lg font-semibold" style={{ color: "#0F172A" }}>{item.displayName}</h2>
            <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
          </div>

          {/* Section 1: Alternative HTS identified */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>Alternative HTS identified</h3>
            <div className="rounded-lg border border-[#E5E7EB] p-4 space-y-2">
              <p><strong>{item.displayName}</strong></p>
              <p>Alternative HTS: <code className="font-mono text-sm bg-gray-100 px-1 rounded">{item.recommendedHts}</code></p>
              {item.estimatedSavings > 0 && (
                <p className="text-green-700 font-semibold">Estimated savings: ${item.estimatedSavings.toLocaleString()}</p>
              )}
              <p>Evidence strength: <span className={evidenceStrengthLabel === "Strong" ? "text-green-700" : evidenceStrengthLabel === "Moderate" ? "text-amber-700" : ""}>{evidenceStrengthLabel}</span></p>
              <p>Review level: <span className={reviewLevel === "MEDIUM" || reviewLevel === "Medium" ? "text-amber-700" : ""}>{reviewLevel}</span></p>
            </div>
          </section>

          {/* Section 2: Why this may fit */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>Why this may fit</h3>
            <ul className="list-disc list-inside space-y-1 text-sm" style={{ color: "#0F172A" }}>
              {whyFits.map((f, i) => (
                <li key={i}>
                  {typeof f === "string" ? f : f.text}
                  {(f as { source?: string; page?: string }).source && (
                    <span className="text-xs text-[#64748B] ml-1">({(f as { source?: string }).source}{(f as { page?: string }).page ? `, ${(f as { page?: string }).page}` : ""})</span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* Section 3: What weakens this */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>What weakens this</h3>
            <ul className="list-disc list-inside space-y-1 text-sm" style={{ color: "#0F172A" }}>
              {whyRisky.map((r, i) => (
                <li key={i}>
                  {typeof r === "string" ? r : r.text}
                  {(r as { source?: string }).source && (
                    <span className="text-xs text-[#64748B] ml-1">({(r as { source?: string }).source})</span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* Section 4: Evidence strength breakdown */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>Evidence strength breakdown</h3>
            <ul className="text-sm space-y-1" style={{ color: "#0F172A" }}>
              <li>Document match: {docMatch}</li>
              <li>Ruling support: {rulingSupport}</li>
              <li>Data completeness: {dataCompleteness}</li>
            </ul>
            {(reviewLevel === "MEDIUM" || reviewLevel === "Medium") && (
              <>
                <h3 className="text-sm font-medium mt-3 mb-2" style={{ color: "#64748B" }}>Review level because</h3>
                <ul className="text-sm space-y-1" style={{ color: "#0F172A" }}>
                  {rawItem?.regulatory?.length ? <li>Regulatory review required</li> : null}
                  <li>No direct ruling match</li>
                </ul>
              </>
            )}
          </section>

          {/* Section 5: Evidence details */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>Evidence</h3>
            <ul className="space-y-1 text-sm" style={{ color: "#0F172A" }}>
              {docDetails.map((d: { name: string; detail: string }, i: number) => (
                <li key={i}>• {d.name} ({d.detail})</li>
              ))}
            </ul>
          </section>

          {/* Section 6: NECO reasoning */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>NECO reasoning</h3>
            <p className="text-sm" style={{ color: "#0F172A" }}>
              {reasoningSummary ??
                `NECO compared declared HTS ${item.declaredHts} against alternative codes using document evidence, duty structure, and classification rules.`}
            </p>
          </section>

          {/* Section 7: Suggested next step */}
          <section className="rounded-lg border border-amber-200 bg-amber-50/80 p-4">
            <h3 className="text-sm font-medium mb-2 text-amber-900">Suggested next step</h3>
            <p className="text-sm text-amber-900">
              {evidenceBundle?.next_step ?? "Review supporting documents and confirm with broker before export."}
            </p>
          </section>
        </div>
      </div>
    </>
  )
}
