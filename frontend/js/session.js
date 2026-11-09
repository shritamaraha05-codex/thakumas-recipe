// session.js - Authentication session protection for pages
import { getSession, signOut } from './auth.js'
import { supabaseConfigured } from './supabase.js'

/**
 * Ensures user is authenticated on a protected page.
 * If not, redirects to login.html.
 * Returns { session, user, token } on success.
 */
export async function requireAuth({ redirectTo = '/login.html' } = {}) {
  // If Supabase is not configured at all in local dev, allow inspecting UI or redirect
  if (!supabaseConfigured) {
    console.warn('[session] Supabase is not configured (VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY missing).')
    return { session: null, user: null, token: null, unconfigured: true }
  }

  try {
    const { data: { session }, error } = await getSession()
    if (error || !session) {
      window.location.replace(redirectTo)
      return new Promise(() => {}) // Halt further execution while navigating
    }

    return {
      session,
      user: session.user,
      token: session.access_token,
      unconfigured: false,
    }
  } catch (err) {
    console.error('[session] Error checking session:', err)
    window.location.replace(redirectTo)
    return new Promise(() => {})
  }
}

/**
 * For login / entry pages: if user is already authenticated,
 * redirect them directly to the library.
 */
export async function redirectIfAuthenticated({ redirectTo = '/library.html' } = {}) {
  if (!supabaseConfigured) return null

  try {
    const { data: { session } } = await getSession()
    if (session) {
      window.location.replace(redirectTo)
      return session
    }
  } catch (err) {
    console.warn('[session] Check failed:', err)
  }
  return null
}

/**
 * Log out and redirect to login.html
 */
export async function logoutUser({ redirectTo = '/login.html' } = {}) {
  try {
    await signOut()
  } catch (err) {
    console.warn('[session] Sign out error:', err)
  }
  window.location.replace(redirectTo)
}

