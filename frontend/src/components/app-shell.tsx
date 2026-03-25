/**
 * AppShell - Sprint 12
 *
 * Main application shell with top bar (org selector, user menu) and left nav.
 * In dev mode with dev token, shows simplified header without Clerk components.
 */

"use client"

import { UserButton, OrganizationSwitcher } from "@clerk/nextjs"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Package } from "lucide-react"

type RuntimeTrust = {
  environment?: string
  classification_rule_mode?: string
  sprint12_inline_analysis_dev?: boolean
  sprint12_sync_analysis_dev?: boolean
  sprint12_fast_analysis_dev?: boolean
  sprint12_instant_analysis_dev?: boolean
}

export function AppShell({
  children,
  isDevAuth = false,
}: {
  children: React.ReactNode
  isDevAuth?: boolean
}) {
  const router = useRouter()
  const [runtimeTrust, setRuntimeTrust] = useState<RuntimeTrust | null>(null)

  useEffect(() => {
    let cancelled = false
    const base = typeof window !== "undefined" ? window.location.origin : ""
    fetch(`${base}/api/v1/runtime-trust`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setRuntimeTrust(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const showTrustBanner =
    runtimeTrust &&
    (runtimeTrust.environment !== "production" ||
      runtimeTrust.sprint12_instant_analysis_dev ||
      runtimeTrust.sprint12_fast_analysis_dev ||
      (runtimeTrust.classification_rule_mode &&
        String(runtimeTrust.classification_rule_mode).toLowerCase() !== "enforce"))

  const handleDevLogout = () => {
    document.cookie = "neco_dev_token=; path=/; max-age=0"
    document.cookie = "neco_dev_org_id=; path=/; max-age=0"
    router.push("/dev-login")
    router.refresh()
  }

  return (
    <div className="min-h-screen bg-background">
      {showTrustBanner && runtimeTrust && (
        <div
          className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-950"
          role="status"
        >
          <strong className="font-semibold">Trust / dev runtime:</strong>{" "}
          env={runtimeTrust.environment ?? "—"} · rule_mode=
          {runtimeTrust.classification_rule_mode ?? "—"} · inline=
          {String(runtimeTrust.sprint12_inline_analysis_dev)} · sync=
          {String(runtimeTrust.sprint12_sync_analysis_dev)} · fast=
          {String(runtimeTrust.sprint12_fast_analysis_dev)} · instant=
          {String(runtimeTrust.sprint12_instant_analysis_dev)}
          <span className="text-amber-800 ml-2">
            Analysis path and flags may differ from production; confirm outcomes against source documents.
          </span>
        </div>
      )}
      {/* Top Bar */}
      <header className="border-b">
        <div className="flex h-16 items-center px-6 justify-between">
          <div className="flex items-center gap-6">
            <Link href="/app/shipments" className="flex items-center gap-2">
              <Package className="h-6 w-6" />
              <span className="font-semibold">NECO</span>
            </Link>
            {isDevAuth ? (
              <span className="text-sm text-gray-500">Dev User (org_s12_loop)</span>
            ) : (
              <OrganizationSwitcher
                hidePersonal={true}
                organizationProfileMode="navigation"
                organizationProfileUrl="/app/organizations/:id"
              />
            )}
          </div>
          {isDevAuth ? (
            <button
              onClick={handleDevLogout}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Dev Logout
            </button>
          ) : (
            <UserButton />
          )}
        </div>
      </header>

      <div className="flex">
        {/* Left Nav */}
        <aside className="w-64 border-r min-h-[calc(100vh-4rem)]">
          <nav className="p-4 space-y-2">
            <Link
              href="/app/shipments"
              className="block px-4 py-2 rounded-md hover:bg-accent text-sm font-medium"
            >
              Shipments
            </Link>
            <Link
              href="/app/psc-radar"
              className="block px-4 py-2 rounded-md hover:bg-accent text-sm font-medium"
            >
              PSC Radar
            </Link>
            <Link
              href="/app/signal-health"
              className="block px-4 py-2 rounded-md hover:bg-accent text-sm font-medium"
            >
              Signal Health
            </Link>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
