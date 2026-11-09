// auth.js - Reusable authentication methods wrapping Supabase Auth
import { supabase, supabaseConfigured } from './supabase.js'

function ensureSupabase() {
  if (!supabaseConfigured || !supabase) {
    throw new Error('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.')
  }
}

export async function signUp({ email, password, data = {} }) {
  ensureSupabase()
  return await supabase.auth.signUp({
    email,
    password,
    options: {
      data,
    },
  })
}

export async function signIn({ email, password }) {
  ensureSupabase()
  return await supabase.auth.signInWithPassword({
    email,
    password,
  })
}

export async function signInWithGoogle() {
  ensureSupabase()
  return await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/library.html`,
    },
  })
}

export async function signOut() {
  if (!supabase) return { error: null }
  return await supabase.auth.signOut()
}

export async function getSession() {
  if (!supabase) return { data: { session: null }, error: null }
  return await supabase.auth.getSession()
}

export async function getCurrentUser() {
  if (!supabase) return null
  const { data: { session } } = await supabase.auth.getSession()
  return session?.user || null
}

export function onAuthStateChange(callback) {
  if (!supabase) return { data: { subscription: { unsubscribe: () => {} } } }
  return supabase.auth.onAuthStateChange(callback)
}

