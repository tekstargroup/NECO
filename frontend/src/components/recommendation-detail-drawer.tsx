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
  isPreCompliance?: boolean
  item: {
    displayName: string
    declaredHts: string
    recommendedHts: string
    currentDutyRate?: string
    countryOfOrigin?: string
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
  isPreCompliance = false,
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
    if (item.estimatedSavings > 0) whyFits.push({ text: `${isPreCompliance ? "Likely HS code suggestion" : "Alternative HTS"} shows lower duty rate based on comparable data.` })
    if (rawItem?.psc?.alternatives?.length) whyFits.push({ text: "Historical usage and PSC signals align with similar imports." })
    if (rawItem?.classification?.primary_candidate) whyFits.push({ text: "Classification engine identified matching HTS structure." })
    if (whyFits.length === 0) whyFits.push({ text: `${isPreCompliance ? "Likely HS code suggestion" : "Alternative classification"} identified from document analysis.` })
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

          {/* Section 1: Classification suggestion */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>{isPreCompliance ? "Likely HS code suggestion" : "Alternative HTS identified"}</h3>
            <div className="rounded-lg border border-[#E5E7EB] p-4 space-y-2">
              <p><strong>{item.displayName}</strong></p>
              <p>{isPreCompliance ? "Likely HS code" : "Alternative HTS"}: <code className="font-mono text-sm bg-gray-100 px-1 rounded">{item.recommendedHts}</code></p>
              <p>Current duty rate (item + COO): <strong>{item.currentDutyRate || "Pending duty resolution"}</strong> ({item.countryOfOrigin || "COO not provided"})</p>
              {!isPreCompliance && item.estimatedSavings > 0 && (
                <p className="text-green-700 font-semibold">Estimated savings: ${item.estimatedSavings.toLocaleString()}</p>
              )}
              <p>Evidence strength: <span className={evidenceStrengthLabel === "Strong" ? "text-green-700" : evidenceStrengthLabel === "Moderate" ? "text-amber-700" : ""}>{evidenceStrengthLabel}</span></p>
              <p>Review level: <span className={reviewLevel === "MEDIUM" || reviewLevel === "Medium" ? "text-amber-700" : ""}>{reviewLevel}</span></p>
            </div>
          </section>

          {/* Prior knowledge notice */}
          {rawItem?.prior_knowledge && (
            <section>
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 space-y-1">
                <h3 className="text-sm font-semibold text-blue-900">Prior classification found</h3>
                <p className="text-sm text-blue-800">
                  HTS: <code className="font-mono bg-blue-100 px-1 rounded">{rawItem.prior_knowledge.prior_hts_code}</code>
                  {rawItem.prior_knowledge.source_review_id && (
                    <span className="text-xs text-blue-600 ml-2">from review {rawItem.prior_knowledge.source_review_id.slice(0, 8)}...</span>
                  )}
                </p>
                {rawItem.prior_knowledge.accepted_by && (
                  <p className="text-xs text-blue-700">Accepted by: {rawItem.prior_knowledge.accepted_by} {rawItem.prior_knowledge.accepted_at ? `on ${new Date(rawItem.prior_knowledge.accepted_at).toLocaleDateString()}` : ""}</p>
                )}
                <p className="text-xs text-blue-600 mt-1 font-medium">Review before applying — not auto-applied</p>
              </div>
            </section>
          )}

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
            {rawItem?.evidence_used?.length > 0 ? (
              <div className="space-y-2">
                {rawItem.evidence_used.map((ev: any, i: number) => (
                  <div key={i} className="rounded border border-slate-200 p-2 text-sm">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex rounded bg-blue-50 text-blue-700 px-1.5 py-0.5 text-[10px] font-medium">{ev.document_type?.replace(/_/g, " ") || "Doc"}</span>
                      <span className="font-medium">{ev.filename}</span>
                      <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        ev.match_confidence === "high" ? "bg-green-50 text-green-700" :
                        ev.match_confidence === "medium" ? "bg-slate-100 text-slate-600" :
                        "bg-amber-50 text-amber-700"
                      }`}>
                        {ev.match_confidence === "high" ? "Match: HIGH (linked)" :
                         ev.match_confidence === "medium" ? "Match: MEDIUM" :
                         "Match: LOW (filename only)"}
                      </span>
                    </div>
                    {ev.snippet && (
                      <p className="mt-1 text-xs text-slate-600 leading-relaxed">&quot;{ev.snippet.slice(0, 200)}{ev.snippet.length > 200 ? "…" : ""}&quot;</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <ul className="space-y-1 text-sm" style={{ color: "#0F172A" }}>
                {docDetails.map((d: { name: string; detail: string }, i: number) => (
                  <li key={i}>• {d.name} ({d.detail})</li>
                ))}
              </ul>
            )}
          </section>

          {/* Section 5b: Authority references */}
          {evidenceBundle?.authority_refs && evidenceBundle.authority_refs.length > 0 && (
            <section>
              <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>Authority references</h3>
              <ul className="space-y-1 text-sm" style={{ color: "#0F172A" }}>
                {evidenceBundle.authority_refs.map((ref, i) => (
                  <li key={i}>
                    • <strong>{ref.authority_type}</strong>
                    {ref.reference_id ? ` ${ref.reference_id}` : ""}
                    {ref.title ? ` — ${ref.title}` : ""}
                    {ref.relation ? ` (${ref.relation})` : ""}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Section 6: NECO reasoning */}
          <section>
            <h3 className="text-sm font-medium mb-2" style={{ color: "#64748B" }}>NECO reasoning</h3>
            <p className="text-sm" style={{ color: "#0F172A" }}>
              {(evidenceBundle as any)?.explanation_summary ||
                reasoningSummary ||
                `NECO compared declared HTS ${item.declaredHts} against ${isPreCompliance ? "likely HS code suggestions" : "alternative codes"} using document evidence, duty structure, and classification rules.`}
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
