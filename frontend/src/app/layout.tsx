import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { ClerkProvider } from "@clerk/nextjs"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "NECO - Next-Gen Compliance Engine",
  description: "Compliance infrastructure for U.S. Customs",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider
      afterSignInUrl="/app/organizations/select"
      afterSignUpUrl="/app/organizations/select"
    >
      <html lang="en" suppressHydrationWarning>
        <body className={inter.className} suppressHydrationWarning>
          {children}
        </body>
      </html>
    </ClerkProvider>
  )
}
