/**
 * Returns true if the given user email is in the VITE_ADMIN_EMAILS list.
 *
 * VITE_ADMIN_EMAILS is a comma-separated list of admin email addresses set in
 * the frontend .env file, e.g.: VITE_ADMIN_EMAILS=you@example.com,other@example.com
 *
 * This is UI-gating only — the backend enforces the real access check via
 * the require_admin decorator. Never rely solely on client-side access control.
 */
export function isAdminEmail(email: string | undefined | null): boolean {
  if (!email) return false;
  const raw = (import.meta.env.VITE_ADMIN_EMAILS as string) ?? "";
  const adminList = raw
    .split(",")
    .map((e: string) => e.trim().toLowerCase())
    .filter(Boolean);
  return adminList.includes(email.toLowerCase());
}
