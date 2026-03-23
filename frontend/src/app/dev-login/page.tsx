"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9001";
const DEV_AUTH = process.env.NEXT_PUBLIC_DEV_AUTH === "true";

function setDevCookie(name: string, value: string, maxAgeDays: number) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${
    maxAgeDays * 24 * 60 * 60
  }; SameSite=Lax`;
}

export default function DevLoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!DEV_AUTH) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Dev auth is disabled.</p>
      </div>
    );
  }

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/dev-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const { access_token, org_id } = await res.json();
      setDevCookie("neco_dev_token", access_token, 7);
      setDevCookie("neco_dev_org_id", org_id, 7);
      router.push("/app/shipments");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gray-50">
      <h1 className="text-xl font-semibold text-gray-800">Dev Login</h1>
      <p className="text-sm text-gray-500">
        Bypass Clerk for local testing. Requires Sprint 12 seed data.
      </p>
      <button
        onClick={handleLogin}
        disabled={loading}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? "Logging in..." : "Login as test user (dev only)"}
      </button>
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
