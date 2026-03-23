/**
 * Organization Selection Page - Sprint 12
 * 
 * Shown when no organization is selected.
 * Redirects after org selection.
 */

"use client"

import { useOrganization, useOrganizationList } from "@clerk/nextjs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"
import { useState } from "react"

export default function SelectOrganizationPage() {
  const { userMemberships, isLoaded, setActive } = useOrganizationList()
  const { organization } = useOrganization()
  const [continuing, setContinuing] = useState(false)

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  const handleOrgSelect = async (orgId: string) => {
    try {
      await setActive({ organization: orgId })
      window.location.assign("/app/shipments")
    } catch (error) {
      console.error("Failed to set active organization:", error)
    }
  }

  const handleContinue = async () => {
    if (!organization) return
    try {
      setContinuing(true)
      await setActive({ organization: organization.id })
      window.location.assign("/app/shipments")
    } catch (error) {
      console.error("Failed to continue with active organization:", error)
      setContinuing(false)
    }
  }

  const organizations = userMemberships?.data?.map((m) => m.organization) || []

  return (
    <div className="flex items-center justify-center min-h-screen p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Select Organization</CardTitle>
          <CardDescription>
            Please select an organization to continue.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {organization ? (
            <div className="mb-4 rounded-md border bg-muted/40 p-3">
              <p className="text-sm">
                Active organization: <span className="font-medium">{organization.name || organization.id}</span>
              </p>
              <div className="mt-3">
                <Button onClick={handleContinue} variant="outline" disabled={continuing}>
                  {continuing ? "Continuing..." : "Continue to Shipments"}
                </Button>
              </div>
            </div>
          ) : null}
          {organizations.length > 0 ? (
            <div className="space-y-2">
              {organizations.map((org) => (
                <Button
                  key={org.id}
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => handleOrgSelect(org.id)}
                >
                  {org.name || org.id}
                </Button>
              ))}
            </div>
          ) : !organization ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                No organizations are provisioned for this account in NECO yet.
                Ask an administrator to provision your organization membership.
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
