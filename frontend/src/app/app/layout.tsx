/**
 * App Layout - Sprint 12
 *
 * Protected app shell with Clerk auth and org selection.
 * In dev mode with dev token cookie, skips Clerk auth.
 */

import { auth } from "@clerk/nextjs/server"
import { cookies } from "next/headers"
import { AppShell } from "@/components/app-shell"
import { DevAuthProvider } from "@/contexts/dev-auth-context"

const isDevAuthEnv = process.env.NEXT_PUBLIC_DEV_AUTH === "true"

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  if (isDevAuthEnv) {
    const cookieStore = await cookies()
    const devToken = cookieStore.get("neco_dev_token")?.value
    const devOrgId = cookieStore.get("neco_dev_org_id")?.value ?? null
    if (devToken) {
      return (
        <DevAuthProvider isDevAuth orgId={devOrgId}>
          <AppShell isDevAuth>{children}</AppShell>
        </DevAuthProvider>
      )
    }
  }

  await auth()
  return (
    <DevAuthProvider isDevAuth={false} orgId={null}>
      <AppShell isDevAuth={false}>{children}</AppShell>
    </DevAuthProvider>
  )
}
