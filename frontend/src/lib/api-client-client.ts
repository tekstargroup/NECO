/**
 * Client-Side API Client - Sprint 12
 *
 * For use in Client Components only.
 * Uses Clerk's useAuth() hook to get user/org IDs.
 * In dev mode (NEXT_PUBLIC_DEV_AUTH=true), uses dev token cookie instead.
 */

"use client";

import { useAuth } from "@clerk/nextjs";
import { useOrganization } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

const USE_PROXY = process.env.NEXT_PUBLIC_USE_API_PROXY === "true";
const API_BASE_URL = USE_PROXY ? "" : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:9001");
const TEST_ORG_ID = process.env.NEXT_PUBLIC_TEST_ORG_ID || null;
const DEV_AUTH = process.env.NEXT_PUBLIC_DEV_AUTH === "true";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export interface ApiError {
  detail?: string | Array<{ type?: string; loc?: unknown; msg?: string; input?: unknown; ctx?: unknown; url?: string }>;
  error?: string;
  message?: string;
  errors?: Record<string, string[]>;
}

/**
 * Format API error for display. Handles FastAPI validation errors (array of objects).
 * Provides helpful hints for "Failed to fetch" (backend unreachable).
 */
export function formatApiError(e: ApiClientError | { data?: ApiError; message?: string }): string {
  const msg = (e as Error).message || "";
  if (
    msg.toLowerCase().includes("failed to fetch") ||
    msg.toLowerCase().includes("networkerror") ||
    msg.toLowerCase().includes("network request failed")
  ) {
    const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9001";
    return `Cannot reach the API at ${base}. Make sure the backend is running (./start_neco.sh).`;
  }
  const data = "data" in e ? e.data : undefined;
  const detail = data?.detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => (typeof d === "object" && d?.msg ? d.msg : String(d)))
      .join("; ");
  }
  if (typeof detail === "string") return detail;
  if (data?.error) return data.error;
  if (data?.message) return data.message;
  return msg || "An error occurred";
}

export class ApiClientError extends Error {
  constructor(public status: number, public data: ApiError, message?: string) {
    const msg = message || (typeof data.detail === "string" ? data.detail : data.error) || `API error: ${status}`;
    super(msg);
    this.name = "ApiClientError";
  }
}

/**
 * Client-side API client hook.
 * Returns functions that include auth headers.
 */
export function useApiClient() {
  const { userId, orgId, getToken } = useAuth()
  const { organization } = useOrganization()
  const router = useRouter();

  const devToken = DEV_AUTH ? getCookie("neco_dev_token") : null;
  const devOrgId = DEV_AUTH ? getCookie("neco_dev_org_id") : null;
  const useDevAuth = !!devToken && !!devOrgId;

  const effectiveOrgId = useDevAuth
    ? devOrgId
    : orgId || organization?.id || TEST_ORG_ID || null;

  const apiClient = async <T = unknown>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> => {
    const token = useDevAuth ? devToken : await getToken();

    if (!useDevAuth && !userId) {
      router.push("/sign-in");
      throw new Error("Not authenticated");
    }
    if (!effectiveOrgId) {
      throw new ApiClientError(403, { detail: "Organization required" }, "Organization required");
    }
    if (!token) {
      if (useDevAuth) router.push("/dev-login");
      else router.push("/sign-in");
      throw new Error("No auth token");
    }

    const url = `${API_BASE_URL}${endpoint}`;
    if (typeof window !== "undefined" && (options.method === "POST" || options.method === "GET")) {
      console.log("[NECO] API", options.method || "GET", url)
    }

    const mergedHeaders = { ...(options.headers || {}) } as Record<string, string>

    delete mergedHeaders.Authorization
    delete mergedHeaders.authorization
    delete mergedHeaders["X-Clerk-User-Id"]
    delete mergedHeaders["x-clerk-user-id"]
    
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "X-Clerk-Org-Id": effectiveOrgId,
      ...mergedHeaders,
    }
    

    const response = await fetch(url, {
      ...options,
      headers,
    });

    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
      if (response.status === 401) {
        router.push(useDevAuth ? "/dev-login" : "/sign-in");
      }
      const text = await response.text();
      let data: ApiError;
      try {
        data = text ? (JSON.parse(text) as ApiError) : { detail: "Request failed" };
      } catch {
        data = { detail: text || `API error: ${response.status}` };
      }
      throw new ApiClientError(response.status, data);
    }

    if (response.status === 204 || response.headers.get("content-length") === "0") {
      return undefined as T;
    }
    const text = await response.text();
    if (!text) return undefined as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      return undefined as T;
    }
  };

  const apiGet = async <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClient<T>(endpoint, { method: "GET", ...options });
  };

  /** GET and return response as Blob (e.g. for file download with auth). */
  const apiGetBlob = async (endpoint: string): Promise<Blob> => {
    const token = useDevAuth ? devToken : await getToken();
    if (!useDevAuth && !userId) {
      router.push("/sign-in");
      throw new Error("Not authenticated");
    }
    if (!effectiveOrgId) {
      throw new ApiClientError(403, { detail: "Organization required" }, "Organization required");
    }
    if (!token) {
      if (useDevAuth) router.push("/dev-login");
      else router.push("/sign-in");
      throw new Error("No auth token");
    }
    const url = `${API_BASE_URL}${endpoint}`;
    const headers: HeadersInit = {
      Authorization: `Bearer ${token}`,
      "X-Clerk-Org-Id": effectiveOrgId,
    };
    const response = await fetch(url, { method: "GET", headers });
    if (!response.ok) {
      const text = await response.text();
      let data: ApiError;
      try {
        data = text ? (JSON.parse(text) as ApiError) : { detail: "Request failed" };
      } catch {
        data = { detail: text || `API error: ${response.status}` };
      }
      throw new ApiClientError(response.status, data);
    }
    return response.blob();
  };

  const apiPost = async <T = unknown>(
    endpoint: string,
    body?: unknown,
    extraOptions?: RequestInit
  ): Promise<T> => {
    return apiClient<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      ...extraOptions,
    });
  };

  /** POST FormData (e.g. file upload). Omits Content-Type so browser sets multipart boundary. */
  const apiPostForm = async <T = unknown>(
    endpoint: string,
    formData: FormData,
    extraOptions?: RequestInit
  ): Promise<T> => {
    const token = useDevAuth ? devToken : await getToken();
    if (!useDevAuth && !userId) {
      router.push("/sign-in");
      throw new Error("Not authenticated");
    }
    if (!effectiveOrgId) {
      throw new ApiClientError(403, { detail: "Organization required" }, "Organization required");
    }
    if (!token) {
      if (useDevAuth) router.push("/dev-login");
      else router.push("/sign-in");
      throw new Error("No auth token");
    }
    const url = `${API_BASE_URL}${endpoint}`;
    const headers: HeadersInit = {
      Authorization: `Bearer ${token}`,
      "X-Clerk-Org-Id": effectiveOrgId,
      ...(extraOptions?.headers || {}),
    };
    delete (headers as Record<string, unknown>)["Content-Type"];
    const response = await fetch(url, {
      method: "POST",
      body: formData,
      headers,
      ...extraOptions,
    });
    if (!response.ok) {
      const text = await response.text();
      let data: ApiError;
      try {
        data = text ? (JSON.parse(text) as ApiError) : { detail: "Request failed" };
      } catch {
        data = { detail: text || `API error: ${response.status}` };
      }
      throw new ApiClientError(response.status, data);
    }
    const text = await response.text();
    if (!text) return undefined as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      return undefined as T;
    }
  };

  const apiPatch = async <T = unknown>(
    endpoint: string,
    body?: unknown
  ): Promise<T> => {
    return apiClient<T>(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  };

  const apiDelete = async (endpoint: string): Promise<void> => {
    await apiClient(endpoint, { method: "DELETE" });
  };

  const apiPut = async (
    endpoint: string,
    body: Blob | ArrayBuffer,
    headers?: HeadersInit
  ): Promise<Response> => {
    const putToken = useDevAuth ? devToken : await getToken();
    if (!useDevAuth && !userId) {
      router.push("/sign-in");
      throw new Error("Not authenticated");
    }
    if (!effectiveOrgId) {
      throw new ApiClientError(403, { detail: "Organization required" }, "Organization required");
    }
    if (!putToken) {
      if (useDevAuth) router.push("/dev-login");
      else router.push("/sign-in");
      throw new Error("No auth token");
    }

    const url = endpoint.startsWith("http")
      ? endpoint
      : `${API_BASE_URL}${endpoint}`;

    const requestHeaders: HeadersInit = {
      Authorization: `Bearer ${putToken}`,
      "X-Clerk-Org-Id": effectiveOrgId,
      ...(headers || {}),
    };

    const response = await fetch(url, {
      method: "PUT",
      body,
      headers: requestHeaders,
    });

    if (!response.ok) {
      throw new Error(
        `Upload failed: ${response.status} ${response.statusText}`
      );
    }

    return response;
  };

  return { apiGet, apiPost, apiPostForm, apiPatch, apiPut, apiDelete, apiGetBlob, effectiveOrgId, useDevAuth };
}
