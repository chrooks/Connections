/**
 * Supabase client configuration.
 *
 * Initializes and exports the Supabase client instance used for
 * authentication throughout the application.
 */

import { createClient } from "@supabase/supabase-js";

// Environment variables for Supabase configuration
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Validate environment variables are present at startup
if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "Missing Supabase environment variables. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY"
  );
}

// Create and export the Supabase client instance with auth configuration
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    // Persist session to localStorage for page refreshes
    persistSession: true,
    // Automatically refresh token before expiry
    autoRefreshToken: true,
    // Detect session from URL for OAuth redirects
    detectSessionInUrl: true,
  },
});
