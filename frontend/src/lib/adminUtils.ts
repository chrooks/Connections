import { apiRequest } from "./api";

/**
 * Fetches admin status for the currently authenticated user from the backend.
 *
 * The backend checks the user's email against its ADMIN_EMAILS env var —
 * no email addresses are ever sent to or stored on the client.
 *
 * Returns false if the user is not authenticated or the request fails.
 */
export async function fetchIsAdmin(): Promise<boolean> {
  try {
    const res = await apiRequest("/me/is-admin");
    if (!res.ok) return false;
    const json = await res.json();
    return json?.data?.is_admin === true;
  } catch {
    return false;
  }
}
