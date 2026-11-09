// session.js - Authentication session protection for pages
import { getSession, signOut } from './auth.js'
import { supabaseConfigured } from './supabase.js'

/**
 * Ensures user is authenticated on a protected page.
 * If not, redirects to login.html with safe returnTo parameter.
 * Returns { session, user, token } on success.
 */
export async function requireAuth({ redirectTo = '/login.html' } = {}) {
  const currentPath = typeof window !== 'undefined'
    ? `${window.location.pathname}${window.location.search}`
    : ''
  const redirectTarget = `${redirectTo}?returnTo=${encodeURIComponent(currentPath)}`

  // If Supabase is not configured, redirect to login where the configuration banner is displayed
  if (!supabaseConfigured) {
    console.warn('[session] Supabase is not configured (VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY missing).')
    if (typeof window !== 'undefined') {
      window.location.replace(`${redirectTarget}&reason=unconfigured`)
    }
    return new Promise(() => {}) // Halt further page execution
  }

  try {
    const { data: { session }, error } = await getSession()
    if (error || !session) {
      if (typeof window !== 'undefined') {
        window.location.replace(redirectTarget)
      }
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
    if (typeof window !== 'undefined') {
      window.location.replace(redirectTarget)
    }
    return new Promise(() => {})
  }
}

/**
 * For login / entry pages: if user is already authenticated,
 * redirect them directly to the returnTo route or library.
 */
export async function redirectIfAuthenticated({ redirectTo = '/library.html' } = {}) {
  if (!supabaseConfigured) return null

  try {
    const { data: { session } } = await getSession()
    if (session) {
      const params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
      const returnTo = params?.get('returnTo')
      const target = returnTo ? decodeURIComponent(returnTo) : redirectTo
      window.location.replace(target)
      return session
    }
  } catch (err) {
    console.warn('[session] Check failed:', err)
  }
  return null
}

/**
 * Log out and redirect to login.html or landing page
 */
export async function logoutUser({ redirectTo = '/login.html' } = {}) {
  try {
    await signOut()
  } catch (err) {
    console.warn('[session] Sign out error:', err)
  }
  if (typeof window !== 'undefined') {
    window.location.replace(redirectTo)
  }
}
