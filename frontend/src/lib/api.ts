/**
 * API helper module for making authenticated requests to the backend.
 *
 * Provides a fetch wrapper that automatically includes the Supabase
 * auth token in the Authorization header when the user is logged in.
 */

import { supabase } from "./supabase";
import { BASE_URL } from "../config/gameConfig";

/**
 * Makes an authenticated API request to the backend.
 * Automatically includes Authorization header with the current user's access token.
 *
 * @param endpoint - The API endpoint path (without base URL)
 * @param options - Standard fetch options (method, body, etc.)
 * @returns The fetch Response object
 */
export async function apiRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  // Get current session to extract access token
  const {
    data: { session },
  } = await supabase.auth.getSession();

  // Build headers with content type and optional auth token
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  // Add Authorization header if user is authenticated
  if (session?.access_token) {
    (headers as Record<string, string>)["Authorization"] =
      `Bearer ${session.access_token}`;
  }

  // Make request with prepared headers
  return fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });
}

/**
 * Convenience method for GET requests.
 */
export function apiGet(endpoint: string): Promise<Response> {
  return apiRequest(endpoint, { method: "GET" });
}

/**
 * Convenience method for POST requests with JSON body.
 */
export function apiPost(endpoint: string, body: object): Promise<Response> {
  return apiRequest(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
