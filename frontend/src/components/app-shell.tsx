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
import { Package } from "lucide-react"

export function AppShell({
  children,
  isDevAuth = false,
}: {
  children: React.ReactNode
  isDevAuth?: boolean
}) {
  const router = useRouter()

  const handleDevLogout = () => {
    document.cookie = "neco_dev_token=; path=/; max-age=0"
    document.cookie = "neco_dev_org_id=; path=/; max-age=0"
    router.push("/dev-login")
    router.refresh()
  }

  return (
    <div className="min-h-screen bg-background">
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
