/**
 * API helper module for making authenticated requests to the admin backend.
 *
 * Mirrors api.ts but targets the /admin blueprint prefix.
 * The admin endpoints require a valid Supabase JWT whose email appears
 * in the server-side ADMIN_EMAILS env var — requests without a valid token
 * are rejected with 401/403.
 */

import { supabase } from "./supabase";

const ADMIN_BASE_URL =
  (import.meta.env.VITE_ADMIN_BASE_URL as string) ??
  "http://localhost:5000/admin";

/**
 * Makes an authenticated request to an admin endpoint.
 *
 * @param endpoint - The path within /admin (e.g. "/puzzles/rejected")
 * @param options  - Standard fetch options (method, body, etc.)
 */
async function adminApiRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  return fetch(`${ADMIN_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });
}

/** Convenience wrapper for GET requests to the admin API. */
export function adminApiGet(endpoint: string): Promise<Response> {
  return adminApiRequest(endpoint, { method: "GET" });
}

/** Convenience wrapper for POST requests to the admin API. */
export function adminApiPost(
  endpoint: string,
  body: object = {}
): Promise<Response> {
  return adminApiRequest(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Convenience wrapper for PATCH requests to the admin API. */
export function adminApiPatch(
  endpoint: string,
  body: object = {}
): Promise<Response> {
  return adminApiRequest(endpoint, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
