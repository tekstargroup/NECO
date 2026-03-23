/**
 * Server-Side API Client - Sprint 12
 *
 * For use in Server Components and Server Actions only.
 * Uses server-side auth() from @clerk/nextjs/server
 */

import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9001";

export interface ApiError {
  detail?: string;
  error?: string;
  message?: string;
  errors?: Record<string, string[]>;
}

export class ApiClientError extends Error {
  constructor(public status: number, public data: ApiError, message?: string) {
    super(message || data.detail || data.error || `API error: ${status}`);
    this.name = "ApiClientError";
  }
}

/**
 * Server-side API client with auth and error handling.
 */
export async function apiClientServer<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const { userId, orgId, getToken } = await auth();

  if (!userId) {
    redirect("/sign-in");
  }
  if (!orgId) {
    redirect("/app/organizations/select");
  }

  // This returns a Clerk-issued JWT for your backend.
  // If you configured a specific JWT template in Clerk, pass it here.
  // Example: await getToken({ template: "neco" })
  const token = await getToken();

  if (!token) {
    throw new ApiClientError(401, { detail: "No server auth token available" }, "No server auth token");
  }

  const url = `${API_BASE_URL}${endpoint}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(orgId ? { "X-Clerk-Org-Id": orgId } : {}),
    ...(options.headers || {}),
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (error: any) {
    if (error?.name === "AbortError") {
      throw new ApiClientError(
        504,
        { detail: "Request timeout - backend may not be running" },
        "Request timeout"
      );
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    if (response.status === 401) {
      throw new ApiClientError(401, { detail: "Unauthorized" }, "Unauthorized");
    }
    if (response.status === 404) throw new ApiClientError(404, { detail: "Not found" }, "Not found");
    throw new ApiClientError(
      response.status,
      { detail: await response.text() },
      `API error: ${response.status}`
    );
  }

  const data = await response.json();

  if (!response.ok) {
    if (response.status === 401) {
      throw new ApiClientError(401, data, "Unauthorized");
    }
    throw new ApiClientError(response.status, data);
  }

  return data as T;
}

export async function apiGetServer<T = unknown>(endpoint: string): Promise<T> {
  return apiClientServer<T>(endpoint, { method: "GET" });
}

export async function apiPostServer<T = unknown>(
  endpoint: string,
  body?: unknown
): Promise<T> {
  return apiClientServer<T>(endpoint, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}
