import { OrganizationProfile } from "@clerk/nextjs"

export default function OrganizationProfilePage() {
  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center p-6">
      <OrganizationProfile routing="path" path="/app/organizations/:id" />
    </div>
  )
}
