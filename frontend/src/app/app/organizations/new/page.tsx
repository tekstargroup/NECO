import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function NewOrganizationPage() {
  return (
    <div className="mx-auto max-w-xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Organization Provisioning Required</h1>
      <p className="text-sm text-muted-foreground">
        Organization creation in the UI is disabled for Sprint 12 because backend access
        requires explicit NECO provisioning. Ask an administrator to create the org mapping
        and membership in the NECO database.
      </p>
      <Link href="/app/organizations/select">
        <Button variant="outline">Back to Organization Selection</Button>
      </Link>
    </div>
  )
}
