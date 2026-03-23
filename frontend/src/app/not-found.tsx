"use client"

import { useRouter } from "next/navigation"
import { useEffect } from "react"

export default function NotFound() {
  const router = useRouter()
  
  const handleReturn = () => {
    router.push("/app/shipments")
  }
  
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <h2 className="text-2xl font-bold mb-4">Not Found</h2>
      <p className="text-muted-foreground mb-4">Could not find requested resource</p>
      <div className="flex gap-4">
        <button
          type="button"
          onClick={handleReturn}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 cursor-pointer"
        >
          Return to Shipments
        </button>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="px-4 py-2 border border-input rounded-md hover:bg-accent cursor-pointer"
        >
          Go Home
        </button>
      </div>
    </div>
  )
}
