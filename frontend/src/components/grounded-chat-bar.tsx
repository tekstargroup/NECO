/**
 * Patch F — Grounded classification Q&A (cite-or-refuse; server uses only stored analysis).
 */

"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useApiClient, formatApiError, ApiClientError } from "@/lib/api-client-client"

type ChatMsg = {
  role: "user" | "assistant"
  text: string
  citations?: { path?: string; label?: string }[]
  refusal?: boolean
}

export function GroundedChatBar({
  shipmentId,
  items,
}: {
  shipmentId: string
  items: { id?: string; label?: string }[]
}) {
  const { apiPost } = useApiClient()
  const [itemId, setItemId] = useState<string>("")
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [loading, setLoading] = useState(false)

  const send = async () => {
    const userMsg = input.trim()
    if (!userMsg) return
    setInput("")
    setMessages((m) => [...m, { role: "user", text: userMsg }])
    setLoading(true)
    try {
      const res = await apiPost<{
        answer: string
        citations?: { path?: string; label?: string }[]
        refusal?: boolean
      }>(`/api/v1/shipments/${shipmentId}/grounded-chat`, {
        message: userMsg,
        shipment_item_id: itemId || undefined,
      })
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: res.answer,
          citations: res.citations,
          refusal: res.refusal,
        },
      ])
    } catch (e: unknown) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: `Could not reach the grounded chat service: ${formatApiError(e as ApiClientError)}`,
          refusal: true,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (!items?.length) return null

  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle className="text-base">Grounded classification Q&A</CardTitle>
        <p className="text-sm text-muted-foreground">
          Answers use only facts, trace, evidence, and classification stored in this run. If it is not in that
          evidence, the reply says so (cite-or-refuse). Even when the run is marked Trusted, duty and PSC fields are
          advisory for Phase 1 — do not treat them as filing authority without separate validation.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length > 1 && (
          <label className="text-sm block">
            Line item
            <select
              className="mt-1 block w-full max-w-md border rounded-md px-2 py-1.5 bg-background text-sm"
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
            >
              <option value="">First line (default)</option>
              {items.map((it) => (
                <option key={it.id} value={it.id}>
                  {(it.label || "Line").slice(0, 60)}
                  {it.id ? ` (${String(it.id).slice(0, 8)}…)` : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="max-h-72 overflow-y-auto space-y-2 text-sm border rounded-md p-2 bg-muted/30">
          {messages.length === 0 && (
            <p className="text-muted-foreground text-xs">
              Try: “Why did you route this here?” · “What fact is missing?” · “What document supports that?” · “What
              alternative heading did you reject?” · “Why are you asking me this question?”
            </p>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={msg.role === "user" ? "text-right" : "text-left"}>
              <div
                className={`inline-block rounded-lg px-3 py-2 max-w-[95%] whitespace-pre-wrap text-left ${
                  msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                {msg.text}
                {msg.refusal && (
                  <div className="mt-1 text-xs opacity-90 border-t border-current/20 pt-1">Refusal / out-of-evidence</div>
                )}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2 text-xs opacity-85 font-mono break-all">
                    <span className="font-sans font-semibold">Citations: </span>
                    {msg.citations.map((c, j) => (
                      <span key={j}>
                        {j > 0 ? " · " : ""}
                        {c.path || c.label || "—"}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <textarea
            className="flex-1 min-h-[44px] border rounded-md px-2 py-1.5 bg-background text-sm"
            placeholder='e.g. "Why did you route this here?"'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                void send()
              }
            }}
            disabled={loading}
          />
          <Button type="button" disabled={loading || !input.trim()} onClick={() => void send()}>
            {loading ? "…" : "Send"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
